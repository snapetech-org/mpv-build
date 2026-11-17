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

FULL_SHA256 = '52c5d84c5a7de70cb346500fdee24764f5d1460f9915cfbc7056ac713946c130'
SEEK_SHA256 = 'be440bed4a56a1af3e031835ced0437a042101cadac2255c1d55df2bd60f1bde'


def check(ffprobe, ffmpeg=None):
    fixture = FIXTURES['av2-fourpeople.ivf']
    with tempfile.TemporaryDirectory() as directory:
        ivf = Path(directory) / fixture.name
        raw = ivf.with_suffix('.obu')
        download(fixture, ivf)
        # Both inputs carry identical coded pictures. The raw demuxer has to
        # discover the stream without the IVF header or record lengths.
        with ivf.open('rb') as src, raw.open('wb') as dst:
            src.seek(32)
            while header := src.read(12):
                size, _ = struct.unpack('<IQ', header)
                payload = src.read(size)
                if len(payload) != size:
                    raise ValueError('Incomplete IVF record')
                dst.write(payload)
        for path in (ivf, raw):
            frames = json.loads(subprocess.check_output([
                ffprobe, '-v', 'error', '-show_entries', 'frame=width,height,pts,pix_fmt',
                '-of', 'json', str(path),
            ], timeout=60))['frames']
            if len(frames) != 130 or any(
                (f['width'], f['height'], f['pix_fmt']) != (480, 270, 'yuv420p') for f in frames
            ):
                raise ValueError(f'{path.name}: incorrect decoded picture count, dimensions or format')
            if path == ivf and [f.get('pts') for f in frames] != list(range(130)):
                raise ValueError('IVF timestamps must advance once per displayed picture')
            if ffmpeg:
                cases = [([], FULL_SHA256)]
                if path == ivf:
                    cases.append((['-ss', '1'], SEEK_SHA256))
                for options, expected in cases:
                    data = subprocess.check_output([
                        ffmpeg, '-v', 'error', *options, '-i', str(path), '-fps_mode', 'passthrough',
                        '-pix_fmt', 'yuv420p', '-f', 'rawvideo', 'pipe:1',
                    ], timeout=60)
                    if hashlib.sha256(data).hexdigest() != expected:
                        raise ValueError(f'{path.name}: wrong pixels after {options}')
            print(f'{path.name}: verified 130 displayed pictures')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ffprobe')
    parser.add_argument('--ffmpeg')
    args = parser.parse_args()
    check(args.ffprobe, args.ffmpeg)
