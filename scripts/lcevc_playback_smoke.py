#!/usr/bin/env python3
"""Require bundled libmpv to reconstruct LCEVC and seek, with base-layer control.

Dimensions distinguish reconstruction from the base layer, not conformance or
pixel fidelity. The local FFmpeg reference comparison is separate evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from codec_playback_smoke import execute

URL = 'https://fate-suite.ffmpeg.org/lcevc/L_H264_640x360p_8bit8bit_2D_dd.ts'
SHA256 = 'f8ba03f69d9e920985311ecf6091d3e8ade84759edb100248107f671be731fcd'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--base', action='store_true')
    args = parser.parse_args()
    if args.worker:
        options = {'vd-lavc-o': 'lcevc-dec-params=passthrough_mode=force'} if args.base else {}
        print(json.dumps(execute(args.library, args.worker, 'video',
            expected_dimensions=(320, 180) if args.base else (640, 360),
            minimum_position=.7, seek_position='0.2', extra_options=options)))
        return
    with tempfile.TemporaryDirectory(prefix='lcevc-playback-') as temporary:
        fixture = Path(temporary) / 'sample.ts'
        with urlopen(URL, timeout=45) as response:
            data = response.read(1024 * 1024)
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError('LCEVC reference fixture hash mismatch')
        fixture.write_bytes(data)
        results = {}
        for name in ('enhanced', 'base'):
            command = [sys.executable, __file__, str(args.library.resolve()), '--worker', str(fixture)]
            if name == 'base':
                command.append('--base')
            result = subprocess.run(command, text=True, capture_output=True, timeout=35)
            if result.returncode:
                raise RuntimeError(f'{name}: {result.stderr[-4000:]}')
            results[name] = json.loads(result.stdout)
    with args.library.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = {'schemaVersion': 1, 'evidence': 'lcevc-reconstruction-dimensions-and-seek',
              'binarySha256': digest, 'architecture': platform.machine(),
              'fixtureUrl': URL, 'fixtureSha256': SHA256, 'results': results,
              'pixelConformanceQualified': False, 'physicalOutputQualified': False}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('LCEVC reconstruction and seek passed: enhanced 640x360; base control 320x180')


if __name__ == '__main__':
    main()
