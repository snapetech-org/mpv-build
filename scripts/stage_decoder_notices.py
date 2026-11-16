#!/usr/bin/env python3
"""Retain dependency copyright terms in the prefix that becomes the package."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def stage(source: Path, prefix: Path, component: str):
    if component not in {'xevd', 'davs2', 'uavs3d', 'lcevc_dec'}:
        raise ValueError('Unknown decoder dependency')
    files = sorted({path for pattern in ('LICENSE*', 'COPYING*', 'NOTICE*') for path in source.glob(pattern)
                    if path.is_file() and not path.is_symlink()})
    if not files:
        raise ValueError(f'{component} has no copyright/license notice')
    if component == 'lcevc_dec' and not {'LICENSE.md', 'COPYING'} <= {path.name for path in files}:
        raise ValueError('LCEVC requires both its license and additional licensing information')
    destination = prefix / 'share/licenses/pleazyng-codecs' / component
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for path in files:
        if path.stat().st_size > 2 * 1024**2:
            raise ValueError('Unexpectedly large dependency notice')
        target = destination / path.name
        shutil.copyfile(path, target)
        hashes[path.name] = hashlib.sha256(target.read_bytes()).hexdigest()
    (destination / 'notice-manifest.json').write_text(json.dumps({'component': component, 'files': hashes}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('prefix', type=Path)
    parser.add_argument('component')
    args = parser.parse_args()
    stage(args.source, args.prefix, args.component)
