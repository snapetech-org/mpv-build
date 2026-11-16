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

    def copy_notice(path: Path, relative: Path):
        if path.is_symlink() or not path.is_file():
            return
        if path.stat().st_size > 2 * 1024**2:
            raise ValueError('Unexpectedly large dependency notice')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        hashes[relative.as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()

    for path in files:
        copy_notice(path, Path(path.name))

    # The LCEVC source tree carries third-party notices separately from its
    # top-level license files. Preserve that complete tree inside the portable
    # notice bundle so Linux, Android/AAR, Apple and Windows retain it.
    if component == 'lcevc_dec':
        nested = sorted(path for path in (source / 'licenses').rglob('*') if path.is_file())
        for path in nested:
            if path.is_symlink():
                continue
            relative = path.relative_to(source / 'licenses')
            copy_notice(path, Path('upstream') / relative)

    manifest = json.dumps({'component': component, 'files': hashes}, indent=2) + '\n'
    (destination / 'notice-manifest.json').write_text(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('prefix', type=Path)
    parser.add_argument('component')
    args = parser.parse_args()
    stage(args.source, args.prefix, args.component)
