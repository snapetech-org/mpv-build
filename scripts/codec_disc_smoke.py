#!/usr/bin/env python3
"""Exercise DVD title playback from a generated, unencrypted VIDEO_TS tree."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from codec_playback_smoke import execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--dvdauthor', default='dvdauthor')
    parser.add_argument('--worker', type=Path)
    args = parser.parse_args()
    if args.worker:
        report = execute(
            args.library, None, 'video', expected_dimensions=(720, 576), minimum_position=2.7,
            seek_position='1.2', extra_options={'dvd-device': str(args.worker), 'end': '2.85'},
            source_uri='dvd://0', minimum_chapters=2,
        )
        args.output.write_text(json.dumps(report), encoding='utf-8')
        return

    with tempfile.TemporaryDirectory(prefix='codec-dvd-') as directory:
        root = Path(directory)
        movie = root / 'movie.mpg'
        disc = root / 'disc'
        subprocess.run([
            args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=720x576:rate=25:duration=3',
            '-f', 'lavfi', '-i', 'sine=frequency=997:sample_rate=48000:duration=3',
            '-ac', '2', '-target', 'pal-dvd', '-threads', '1', str(movie),
        ], check=True, timeout=30)
        settings = ET.Element('dvdauthor', dest=str(disc), format='pal')
        ET.SubElement(settings, 'vmgm')
        titles = ET.SubElement(ET.SubElement(settings, 'titleset'), 'titles')
        pgc = ET.SubElement(titles, 'pgc')
        ET.SubElement(pgc, 'vob', file=str(movie), chapters='0,1,2')
        script = root / 'dvd.xml'
        ET.ElementTree(settings).write(script, encoding='utf-8')
        generated = subprocess.run([args.dvdauthor, '-x', str(script)], capture_output=True, text=True, timeout=30)
        if generated.returncode:
            raise RuntimeError(generated.stderr[-4000:])
        receipt = root / 'worker.json'
        worker = subprocess.run([
            sys.executable, __file__, str(args.library.resolve()), '--worker', str(disc), '--output', str(receipt),
        ], capture_output=True, text=True, timeout=35)
        if worker.returncode:
            raise RuntimeError((worker.stdout + worker.stderr)[-4000:])
        results = json.loads(receipt.read_text(encoding='utf-8'))
        hashes = {str(file.relative_to(disc)): hashlib.sha256(file.read_bytes()).hexdigest()
                  for file in sorted(disc.rglob('*')) if file.is_file()}
    with args.library.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    args.output.write_text(json.dumps({
        'schemaVersion': 1,
        'evidence': 'dvd-title-playback-and-seek',
        'binarySha256': digest,
        'fixtureSha256': hashes,
        'playback': results,
    }, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('Unencrypted authored DVD title played and sought successfully')


if __name__ == '__main__':
    main()
