#!/usr/bin/env python3
"""Inspect packaged MPV bytes and bind an ordered-PCM ABI receipt to their hash.

This does not load native code. Run on a packaging host with a matching symbol
inspector (LLVM binutils or Xcode), after the archive is final. No source or
hardware name is accepted as evidence of a packaged symbol.
"""
from __future__ import annotations
import hashlib
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import zipfile

MAX_ENTRY = 1024 * 1024 * 1024
MAX_TOTAL = 4 * MAX_ENTRY
MAX_ENTRIES = 50000
SYMBOL = 'mpv_plezy_audio_tap_read_next'


def inspect(package: Path, expected: int | None = None) -> dict:
    package = package.resolve(strict=True)
    if package.stat().st_size > MAX_TOTAL:
        raise ValueError('MPV archive exceeds packaging bound')
    digest = hashlib.sha256()
    with package.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    found, names, total = [], set(), 0
    with tempfile.TemporaryDirectory(prefix='mpv-abi-') as temporary:
        def member(name, size, regular, source):
            nonlocal total
            normalized = name.removeprefix('./')
            if normalized in names or len(names) >= MAX_ENTRIES:
                raise ValueError('Duplicate/excess package members')
            names.add(normalized)
            path = PurePosixPath(normalized)
            if path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Unsafe package member')
            base = path.name.lower()
            binary = base in {'libmpv.so', 'libmpv-2.dll', 'libmpv.a'} or base.startswith('libmpv.so.') or (
                base == 'libmpv' and any(p.lower() == 'libmpv.framework' for p in path.parts))
            if not binary or not regular:
                return
            if not 0 < size <= MAX_ENTRY or total + size > MAX_TOTAL:
                raise ValueError('MPV binary size limit')
            total += size
            target = Path(temporary) / (str(len(found)) + '-' + path.name)
            remaining = size
            with source() as reader, target.open('wb') as writer:
                while remaining:
                    block = reader.read(min(1024 * 1024, remaining))
                    if not block: raise ValueError('Truncated MPV binary')
                    writer.write(block)
                    remaining -= len(block)
            subprocess.run([sys.executable, str(Path(__file__).with_name('check_plezy_audio_tap_export.py')),
                            str(target)], check=True, timeout=120)
            found.append(normalized)

        if zipfile.is_zipfile(package):
            with zipfile.ZipFile(package) as archive:
                for info in archive.infolist():
                    mode = info.external_attr >> 16
                    if info.flag_bits & 1: raise ValueError('Encrypted MPV archive')
                    member(info.filename, info.file_size, not info.is_dir() and mode & 0o170000 != 0o120000,
                           lambda info=info: archive.open(info))
        elif package.name.endswith('.tar.zst'):
            process = subprocess.Popen(['zstd', '-q', '-d', '-c', str(package)], stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
            try:
                with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                    for info in archive:
                        member(info.name, info.size, info.isfile(), lambda info=info: archive.extractfile(info))
                process.stdout.close()
                if process.wait(timeout=120): raise ValueError('Invalid zstd package')
            finally:
                if process.poll() is None: process.kill(); process.wait()
        else:
            with tarfile.open(package, mode='r|*') as archive:
                for info in archive:
                    member(info.name, info.size, info.isfile(), lambda info=info: archive.extractfile(info))
    if not found or expected is not None and len(found) != expected:
        raise ValueError(f'Expected {expected or "at least one"} MPV binaries, found {len(found)}')
    return {'orderedSubtitlePcmAbi': 1, 'artifactSha256': digest.hexdigest(),
            'symbol': SYMBOL, 'binaries': sorted(found), 'executionQualified': False}


if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--expected', type=int)
    args = parser.parse_args()
    print(json.dumps(inspect(args.package, args.expected), sort_keys=True))
