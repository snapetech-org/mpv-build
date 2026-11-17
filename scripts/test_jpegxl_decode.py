#!/usr/bin/env python3
"""Decode both JPEG XL forms with the FFprobe built for the native host slice."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from codec_reference_smoke import JPEGXL_FIXTURES, download


def main(ffprobe):
    counts = {'jpegxl-still.jxl': 1, 'jpegxl-animation.jxl': 36}
    with tempfile.TemporaryDirectory() as tmp:
        for name, fixture in JPEGXL_FIXTURES.items():
            path = Path(tmp) / name
            download(fixture, path)
            output = subprocess.check_output([
                ffprobe, '-v', 'error', '-count_frames', '-select_streams', 'v',
                '-show_entries', 'stream=width,height,pix_fmt,nb_read_frames',
                '-of', 'json', str(path),
            ], timeout=45)
            expected = dict(width=fixture.dimensions[0], height=fixture.dimensions[1],
                            pix_fmt=fixture.pixels, nb_read_frames=str(counts[name]))
            streams = json.loads(output)['streams']
            if streams != [expected]:
                raise ValueError(f'{name}: expected {expected}, decoded {streams}')
            print(f'{name}: decoded {counts[name]} frames at {fixture.dimensions}')


if __name__ == '__main__':
    main(sys.argv[1])
