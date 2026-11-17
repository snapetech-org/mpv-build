#!/usr/bin/env python3
"""Check all displayed pictures, timestamps and optional raw pixels on the AV2 build."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from codec_reference_smoke import FIXTURES, download

# Published by the sample author using AVM 01803db6 (samples-v1/samples-manifest.txt).
# avmdec --md5 includes its Y4M header, even when it defaults to 30 fps.
REFERENCE = {
    'av2-fourpeople.ivf': (130, 'yuv420p', '60:1 Ip C420jpeg', 'f4c6de762e3ff80f09cf0524601f3e66'),
    'av2-ritualdance.ivf': (120, 'yuv420p10le', '30:1 Ip C420p10 XYSCSS=420P10', '1e367c9d016191489ddc957ae5a6fd99'),
}
SEEK_SHA256 = 'be440bed4a56a1af3e031835ced0437a042101cadac2255c1d55df2bd60f1bde'


def verify_pixels(ffmpeg, path, width, height, frames, pixels, header, expected):
    frame_size = width * height * 3 // 2 * (2 if pixels == 'yuv420p10le' else 1)
    digest = hashlib.md5(f'YUV4MPEG2 W{width} H{height} F{header}\n'.encode('ascii'))
    command = [ffmpeg, '-v', 'error', '-i', str(path), '-fps_mode', 'passthrough',
               '-pix_fmt', pixels, '-f', 'rawvideo', 'pipe:1']
    with tempfile.TemporaryFile() as decoded:
        subprocess.run(command, stdout=decoded, timeout=120, check=True)
        decoded.seek(0)
        for _ in range(frames):
            picture = decoded.read(frame_size)
            if len(picture) != frame_size:
                raise ValueError(f'{path.name}: missing or incomplete output frame')
            digest.update(b'FRAME\n')
            digest.update(picture)
        if decoded.read(1) or digest.hexdigest() != expected:
            raise ValueError(f'{path.name}: output differs from the AVM reference')


def check(ffprobe, ffmpeg=None):
    with tempfile.TemporaryDirectory() as directory:
        for name, (count, pixels, header, expected) in REFERENCE.items():
            fixture = FIXTURES[name]
            ivf = Path(directory) / name
            download(fixture, ivf)
            paths = [ivf]
            if name == 'av2-fourpeople.ivf':
                # The raw demuxer must discover the stream without IVF record lengths.
                raw = ivf.with_suffix('.obu')
                with ivf.open('rb') as src, raw.open('wb') as dst:
                    src.seek(32)
                    while record := src.read(12):
                        size, _ = struct.unpack('<IQ', record)
                        payload = src.read(size)
                        if len(payload) != size:
                            raise ValueError('Incomplete IVF record')
                        dst.write(payload)
                paths.append(raw)
            for path in paths:
                frames = json.loads(subprocess.check_output([
                    ffprobe, '-v', 'error', '-show_entries', 'frame=width,height,pts,pix_fmt',
                    '-of', 'json', str(path),
                ], timeout=120))['frames']
                if len(frames) != count or any(
                    (f['width'], f['height'], f['pix_fmt']) != (*fixture.dimensions, pixels) for f in frames
                ):
                    raise ValueError(f'{path.name}: incorrect decoded picture count, dimensions or format')
                if path == ivf and [f.get('pts') for f in frames] != list(range(count)):
                    raise ValueError(f'{path.name}: incorrect IVF presentation timestamps')
                if ffmpeg:
                    verify_pixels(ffmpeg, path, *fixture.dimensions, count, pixels, header, expected)
                print(f'{path.name}: verified {count} displayed pictures')
        if ffmpeg:
            data = subprocess.check_output([
                ffmpeg, '-v', 'error', '-ss', '1', '-i', str(Path(directory) / 'av2-fourpeople.ivf'),
                '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1',
            ], timeout=60)
            if hashlib.sha256(data).hexdigest() != SEEK_SHA256:
                raise ValueError('Incorrect IVF pictures after the one-second seek')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ffprobe')
    parser.add_argument('--ffmpeg')
    args = parser.parse_args()
    check(args.ffprobe, args.ffmpeg)
