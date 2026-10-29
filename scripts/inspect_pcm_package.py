#!/usr/bin/env python3
"""Inspect packaged MPV bytes and bind an ordered-PCM ABI receipt to their hash.

This does not load native code. Run on a packaging host with a matching symbol
inspector (LLVM binutils or Xcode), after the archive is final. No source or
hardware name is accepted as evidence of a packaged symbol.
"""
from __future__ import annotations
import hashlib
import plistlib
from pathlib import Path, PurePosixPath
import subprocess
import struct
import sys
import tarfile
import tempfile
import zipfile

MAX_ENTRY = 1024 * 1024 * 1024
MAX_TOTAL = 4 * MAX_ENTRY
MAX_ENTRIES = 50000
SYMBOL = 'mpv_plezy_audio_tap_read_next'
REQUIRED_SYMBOLS = ['mpv_plezy_audio_tap_version', 'mpv_plezy_audio_tap_enable',
                    'mpv_plezy_audio_tap_read', SYMBOL]
APPLE_REQUIRED = {
    ('ios', '', 'arm64'), ('ios', 'simulator', 'arm64'), ('ios', 'simulator', 'x86_64'),
    ('ios', 'maccatalyst', 'arm64'), ('ios', 'maccatalyst', 'x86_64'),
    ('macos', '', 'arm64'), ('macos', '', 'x86_64'),
    ('tvos', '', 'arm64'), ('tvos', '', 'arm64e'),
    ('tvos', 'simulator', 'arm64'), ('tvos', 'simulator', 'x86_64'),
}


def binary_architectures(path: Path) -> list[str]:
    """Read machine headers, not the architecture implied by a file name."""
    with path.open('rb') as stream:
        header = stream.read(64)
        if header[:4] == b'\x7fELF':
            if len(header) < 20 or header[4] not in (1, 2) or header[5] not in (1, 2):
                raise ValueError('Invalid ELF header')
            machine = struct.unpack(('<' if header[5] == 1 else '>') + 'H', header[18:20])[0]
            arch = {(1, 3): 'i386', (1, 40): 'armv7', (2, 62): 'x86_64', (2, 183): 'arm64'}.get((header[4], machine))
            if arch is None: raise ValueError('Unsupported MPV ELF machine')
            return [arch]
        if header[:2] == b'MZ':
            if len(header) < 64: raise ValueError('Truncated PE header')
            offset = struct.unpack('<I', header[60:64])[0]
            if offset < 64 or offset > min(path.stat().st_size - 6, 16 * 1024 * 1024):
                raise ValueError('Invalid PE header offset')
            stream.seek(offset)
            pe = stream.read(6)
            if pe[:4] != b'PE\0\0': raise ValueError('Invalid PE signature')
            arch = {0x14c: 'i386', 0x8664: 'x86_64', 0xaa64: 'arm64'}.get(struct.unpack('<H', pe[4:6])[0])
            if arch is None: raise ValueError('Unsupported MPV PE machine')
            return [arch]
    if sys.platform != 'darwin':
        raise ValueError('Apple archive architecture inspection requires the Apple packaging host')
    result = subprocess.run(['xcrun', 'lipo', '-archs', str(path)], capture_output=True, text=True, timeout=60, check=True)
    archs = result.stdout.split()
    if not archs or len(archs) != len(set(archs)) or not set(archs) <= {'arm64', 'arm64e', 'x86_64'}:
        raise ValueError('Invalid Apple architecture inventory')
    return sorted(archs)


def inspect(package: Path, expected: int | None = None) -> dict:
    package = package.resolve(strict=True)
    if package.stat().st_size > MAX_TOTAL:
        raise ValueError('MPV archive exceeds packaging bound')
    digest = hashlib.sha256()
    with package.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    found, names, hashes, total = [], set(), {}, 0
    architectures, plists = {}, {}
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
            if regular and path.name == 'Info.plist' and path.parent.name.lower().endswith('.xcframework'):
                if size < 1 or size > 256 * 1024: raise ValueError('XCFramework metadata size limit')
                with source() as reader:
                    content = reader.read(size + 1)
                if len(content) != size: raise ValueError('Truncated XCFramework metadata')
                plists[str(path.parent)] = plistlib.loads(content)
                return
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
            binary_digest = hashlib.sha256()
            with source() as reader, target.open('wb') as writer:
                while remaining:
                    block = reader.read(min(1024 * 1024, remaining))
                    if not block: raise ValueError('Truncated MPV binary')
                    writer.write(block)
                    binary_digest.update(block)
                    remaining -= len(block)
            subprocess.run([sys.executable, str(Path(__file__).with_name('check_plezy_audio_tap_export.py')),
                            str(target)], check=True, timeout=120)
            found.append(normalized)
            hashes[normalized] = binary_digest.hexdigest()
            architectures[normalized] = binary_architectures(target)

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
    slices = []
    if any('.xcframework/' in name.lower() for name in found):
        if len(plists) != 1: raise ValueError('Expected one XCFramework metadata document')
        root, metadata = next(iter(plists.items()))
        libraries = metadata.get('AvailableLibraries') if isinstance(metadata, dict) else None
        if not isinstance(libraries, list) or not 1 <= len(libraries) <= 32:
            raise ValueError('Invalid XCFramework library inventory')
        used, coverage = set(), set()
        for library in libraries:
            if not isinstance(library, dict): raise ValueError('Invalid XCFramework library')
            identifier, library_path = library.get('LibraryIdentifier'), library.get('LibraryPath')
            declared = library.get('SupportedArchitectures')
            platform, variant = library.get('SupportedPlatform'), library.get('SupportedPlatformVariant', '')
            if (not isinstance(identifier, str) or PurePosixPath(identifier).name != identifier or
                    identifier in ('', '.', '..') or not isinstance(library_path, str) or
                    PurePosixPath(library_path).name != library_path or library_path in ('', '.', '..') or
                    not isinstance(declared, list) or not declared or any(not isinstance(a, str) for a in declared) or
                    len(declared) != len(set(declared)) or not isinstance(platform, str) or not isinstance(variant, str)):
                raise ValueError('Invalid XCFramework slice declaration')
            prefix = f'{root}/{identifier}/'
            candidates = [name for name in found if name.startswith(prefix)]
            if len(candidates) != 1: raise ValueError('XCFramework slice must contain exactly one MPV binary')
            binary = candidates[0]
            expected_path = prefix + library_path
            if library_path.endswith('.framework'):
                if not binary.startswith(expected_path + '/'): raise ValueError('XCFramework binary path mismatch')
            elif binary != expected_path: raise ValueError('XCFramework archive path mismatch')
            if binary in used or set(architectures[binary]) != set(declared):
                raise ValueError('XCFramework declared architectures differ from the packaged binary')
            used.add(binary)
            for arch in declared:
                item = (platform, variant, arch)
                if item in coverage: raise ValueError('Duplicate XCFramework platform architecture')
                coverage.add(item)
            slices.append({'binary': binary, 'platform': platform, 'variant': variant, 'architectures': sorted(declared)})
        if used != set(found) or not APPLE_REQUIRED <= coverage:
            raise ValueError('MPV XCFramework does not cover every required Apple platform and architecture')
    return {'orderedSubtitlePcmAbi': 1, 'inspectionSchema': 3, 'requiredSymbols': REQUIRED_SYMBOLS, 'artifactSha256': digest.hexdigest(),
            'symbol': SYMBOL, 'binaries': sorted(found), 'binarySha256': hashes,
            'binaryArchitectures': architectures, 'appleSlices': slices, 'executionQualified': False}


if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--expected', type=int)
    args = parser.parse_args()
    print(json.dumps(inspect(args.package, args.expected), sort_keys=True))
