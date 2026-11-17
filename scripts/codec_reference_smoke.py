#!/usr/bin/env python3
"""Exercise pinned decoder reference vectors through the packaged libmpv."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from codec_playback_smoke import execute

FATE = 'https://fate-suite.ffmpeg.org'
AVS2 = 'https://raw.githubusercontent.com/pkuvcl/avs2stream/96065ae3d3f940ebad5a0b84251b3cf27ecf201c'
AVS3 = 'https://raw.githubusercontent.com/uavs3/avs3stream/e9fcc4eac77061213c8fb07c87a8a1106fb66fe8'
AVS2_SAMPLES = 'https://raw.githubusercontent.com/xatabhk/avs2-avs3-video-samples/f5e12f4540784fc6b16dd736caca9ffdac44b038'
MAX_FIXTURE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class Fixture:
    name: str
    url: str
    sha256: str
    dimensions: tuple[int, int]
    pixels: str | None
    min_end: float
    seek: str | None
    repetitions: int = 1
    decode_timeout: int = 12


FIXTURES = {
    fixture.name: fixture
    for fixture in (
        Fixture('av2-ritualdance.ivf',
                'https://github.com/EwoutH/AV2/releases/download/samples-v1/RitualDance_1920x1080_60fps_10bit_420_qp160_120f.ivf',
                'd55a99386094f17e97bef7239eec6d6fe3e564460b59d39dd94e14aa14200ae1',
                (1920, 1080), 'yuv420p10', 1.9, '1', decode_timeout=90),
        Fixture('av2-fourpeople.ivf',
                'https://github.com/EwoutH/AV2/releases/download/samples-v1/FourPeople_480x270_60_qp210_130f.ivf',
                'e7fd3676044bd69a9b96e8702ffac88cb2e5f7735e131a659f522812c008a0f5',
                (480, 270), 'yuv420p', 2.1, '1'),
        Fixture('apv-422-10.apv', f'{FATE}/apv/profile_422-10.apv',
                'abdf4b5e2bf10a6ad8435a5df31f96dde19e0c7f771522db484860966cb9cb77',
                (320, 180), 'yuv422p10', .05, '0.033'),
        # These two elementary streams have a single random-access point.
        # Decode to EOF and verify output. Keep seek evidence separate.
        Fixture('vvc-main10.vvc', f'{FATE}/vvc-conformance/APSMULT_A_4.bit',
                '64abc0029be9aad1e76918d097c8a1556677f6d158426998d856b03cbf9dd08a',
                (416, 240), 'yuv420p10', 1.7, None),
        Fixture('evc-main.evc', f'{FATE}/evc/akiyo_cif.evc',
                'f3ef572163a9354415ab380063137c0907df9cd097c22a7b6be65b351d3c6405',
                (352, 288), 'yuv420p10', 11, None),
        Fixture('avs2-8.avs2', f'{AVS2}/ES/BQSquare_416x240_60_ra/test.avs2',
                '96a662310aae4365b3ad3018040465ea82eb8a77f246cbf15ceb373ccc3096b8',
                (416, 240), 'yuv420p', 1.5, '0.25'),
        Fixture('avs2-main10.mkv', f'{AVS2_SAMPLES}/CCTV4K.AVS2-10bit.AC3.CB.08-27-6s.mkv',
                '60d2902afcc3b716bb075bb26a4a889fe1c98af9ac94fc80f07ec0a36809e7ef',
                (3840, 2160), 'yuv420p10', 5.2, '2', decode_timeout=120),
        Fixture('avs3-8.ts', f'{AVS3}/TS/City_1280x720_60_ra/test.ts',
                '265b35090844f4a9bac98611a986a9aca9ab4a1584400c48b808c640c85713cc',
                (1280, 720), 'yuv420p', 9, '2'),
        Fixture('avs3-10.ts', f'{AVS3}/TS/MarketPlace_1920x1080_60_10bit_ra/test.ts',
                '0b49d812779d971449a2f1f5680449771250f6459e1834cb9610a9ff3d3c88d8',
                (1920, 1080), 'yuv420p10', 9, '2'),
    )
}


JPEGXL_FIXTURES = {
    fixture.name: fixture
    for fixture in (
        Fixture('jpegxl-still.jxl', f'{FATE}/jxl/lenna-256.jxl',
                '005bd5fdc89a263ee8a6d65872d3dd85560498bab7a3896dc0948b49dd2802b7',
                (256, 256), 'rgb24', 0, None),
        Fixture('jpegxl-animation.jxl', f'{FATE}/jxl/newton.jxl',
                '809f336609ed3ae2db11a80f1cb1491e67e073cfc686d3778cb00474c3e93f48',
                (128, 96), 'rgba', .7, None),
    )
}

EVC_TIMELINE = Fixture(
    'evc-two-sequences.mp4', FIXTURES['evc-main.evc'].url, FIXTURES['evc-main.evc'].sha256,
    (352, 288), 'yuv420p10', 23.8, '12.0', repetitions=2,
)


def download(fixture, path):
    with urlopen(fixture.url, timeout=45) as response:
        data = response.read(MAX_FIXTURE_BYTES + 1)
    if len(data) > MAX_FIXTURE_BYTES or hashlib.sha256(data).hexdigest() != fixture.sha256:
        raise ValueError(f'{fixture.name}: reference fixture hash mismatch')
    path.write_bytes(data * fixture.repetitions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--with-jpegxl', action='store_true')
    parser.add_argument('--with-evc-timeline', action='store_true')
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    fixtures = dict(FIXTURES)
    if args.with_jpegxl:
        fixtures.update(JPEGXL_FIXTURES)
    if args.with_evc_timeline:
        fixtures[EVC_TIMELINE.name] = EVC_TIMELINE
    if args.worker:
        fixture = fixtures[args.worker.name]
        report = execute(
            args.library, args.worker, 'video',
            expected_dimensions=fixture.dimensions, minimum_position=fixture.min_end,
            seek_position=fixture.seek, expected_pixel_format=fixture.pixels, decode_timeout=fixture.decode_timeout,
            seek_tolerance=.25 if fixture == EVC_TIMELINE else None,
            extra_options={'untimed': 'yes', 'vd-lavc-threads': '1'} if fixture.name.startswith('evc-')
            else {'untimed': 'yes', 'aid': 'no'},
        )
        args.output.write_text(json.dumps(report), encoding='utf-8')
        return

    results = {}
    with tempfile.TemporaryDirectory(prefix='codec-reference-') as temporary:
        root = Path(temporary)
        flags = []
        if args.with_jpegxl:
            flags.append('--with-jpegxl')
        if args.with_evc_timeline:
            flags.append('--with-evc-timeline')
        for fixture in fixtures.values():
            path = root / fixture.name
            receipt = root / (fixture.name + '.json')
            try:
                if fixture == EVC_TIMELINE:
                    elementary = path.with_suffix('.evc')
                    download(fixture, elementary)
                    mux = subprocess.run([
                        args.ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
                        '-f', 'evc', '-framerate', '25', '-i', str(elementary),
                        '-map', '0:v:0', '-c', 'copy', str(path),
                    ], text=True, capture_output=True, timeout=30)
                    if mux.returncode:
                        raise RuntimeError(mux.stderr[-4000:])
                else:
                    download(fixture, path)
                command = [sys.executable, __file__, str(args.library.resolve()),
                           '--worker', str(path), '--output', str(receipt), *flags]
                result = subprocess.run(command, text=True, capture_output=True, timeout=2 * fixture.decode_timeout + 21)
                if result.returncode:
                    raise RuntimeError((result.stdout + result.stderr)[-4000:])
                case = json.loads(receipt.read_text(encoding='utf-8'))
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
                case = {'error': str(error)}
            results[fixture.name] = {
                **case, 'fixtureUrl': fixture.url, 'fixtureSha256': fixture.sha256,
                'fixtureRepetitions': fixture.repetitions,
            }
            print(f'{fixture.name}: ' + (case.get('error') or 'decode passed; seek ' + case['seek']), flush=True)

    with args.library.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    args.output.write_text(json.dumps({
        'schemaVersion': 1,
        'evidence': 'pinned-reference-playback',
        'binarySha256': digest,
        'architecture': platform.machine(),
        'physicalOutputQualified': False,
        'pixelConformanceQualified': False,
        'results': results,
    }, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    if any('error' in result for result in results.values()):
        raise SystemExit('Native reference playback failures')


if __name__ == '__main__':
    main()
