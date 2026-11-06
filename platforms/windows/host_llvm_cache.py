#!/usr/bin/env python3
"""Reuse verified Linux host LLVM tools across Windows target architectures.

Target wrappers, sysroots, runtimes, and ExternalProject stamps are never
exported. A cache hit has its own validation and installation build steps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 1
MAX_BYTES = 512 * 1024 * 1024
REQUIRED = ('clang', 'clang++', 'ld.lld', 'llvm-ar', 'llvm-nm', 'llvm-readobj')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def normalized_config(text):
    return re.sub(r'/work/build/windows/(aarch64|x86_64)/', '/work/build/windows/ARCH/', text)


def compiler_identity(binary):
    return '\n'.join(line for line in run([binary, '--version']).splitlines()
                     if not line.startswith('InstalledDir:'))


def llvm_pin():
    data = json.loads((ROOT / 'versions.json').read_text())['components']['llvm']
    data = {**data, **data.get('overrides', {}).get('windows', {})}
    return data['commit']


def dynamic_libraries(binary):
    output = run(['ldd', binary])
    if 'not found' in output:
        raise ValueError('Host LLVM has unresolved runtime libraries')
    paths = re.findall(r'(?:=>\s+|^\s*)(/[^\s]+)', output, re.MULTILINE)
    return {Path(p).name: sha(Path(p).resolve()) for p in paths}


def validate_source(source):
    if not (source / '.git').exists():
        raise ValueError('Host LLVM reuse requires the pinned LLVM source checkout for target runtime builds')
    if run(['git', '-C', source, 'rev-parse', 'HEAD']) != llvm_pin():
        raise ValueError('LLVM source checkout differs from versions.json')
    if run(['git', '-C', source, 'diff', '--no-ext-diff', 'HEAD']):
        raise ValueError('LLVM source contains unrecorded changes')


def export(args):
    prefix, stamps = args.prefix.resolve(), args.stamps.resolve()
    validate_source(args.source)
    config = (stamps.parent.parent / 'tmp/llvm-cfgcmd.txt').read_text()
    installed = (stamps / 'llvm-install-out.log').read_text()
    names = {'bin/llvm'}
    for absolute in re.findall(r'^-- (?:Installing|Up-to-date): (.+)$', installed, re.MULTILINE):
        path = Path(absolute)
        if path.is_relative_to(prefix):
            relative = path.relative_to(prefix).as_posix()
            if relative.startswith('bin/') and '/' not in relative[4:]:
                names.add(relative)
    for alias in re.findall(r'^-- Creating ([-+.\w]+)$', installed, re.MULTILINE):
        if alias != 'llvm-config':
            names.add('bin/' + alias)
    for p in (prefix / 'lib/clang/22/include').rglob('*'):
        if p.is_file():
            names.add(p.relative_to(prefix).as_posix())
    files = {}
    for name in sorted(names):
        path = prefix / name
        if path.is_symlink():
            if os.readlink(path) != 'llvm':
                if name[4:] in REQUIRED:
                    raise ValueError(f'Unexpected host tool alias: {name}')
                continue
            files[name] = {'link': 'llvm'}
        elif path.is_file():
            files[name] = {'sha256': sha(path), 'mode': path.stat().st_mode & 0o777}
        else:
            raise ValueError(f'Missing LLVM install entry: {name}')
    for name in REQUIRED:
        if 'bin/' + name not in files:
            raise ValueError(f'Missing host LLVM tool: {name}')
    metadata = {'schema': SCHEMA, 'llvmCommit': llvm_pin(), 'configure': config,
                'normalizedConfigure': normalized_config(config),
                'image': args.image, 'files': files,
                'hostVersion': compiler_identity(prefix / 'bin/clang'),
                'dynamicLibraries': dynamic_libraries(prefix / 'bin/llvm'),
                'packages': run(['dpkg-query', '-W', '-f=${binary:Package}=${Version}\n'])}
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='host-llvm-export-') as temporary:
        receipt = Path(temporary) / 'receipt.json'
        receipt.write_text(json.dumps(metadata, sort_keys=True, indent=2) + '\n')
        with tarfile.open(args.archive, 'x:gz') as archive:
            archive.add(receipt, 'receipt.json')
            for name in sorted(files):
                archive.add(prefix / name, name, recursive=False)
    print(json.dumps({'archive': str(args.archive), 'sha256': sha(args.archive),
                      'llvmCommit': llvm_pin(), 'files': len(files)}))


def unpack(archive, expected_sha, destination):
    if sha(archive) != expected_sha:
        raise ValueError('Host LLVM cache archive checksum mismatch')
    with tarfile.open(archive, 'r:gz') as bundle:
        members = bundle.getmembers()
        if len(members) > 5000 or sum(m.size for m in members) > MAX_BYTES:
            raise ValueError('Host LLVM cache exceeds extraction bounds')
        names = [m.name for m in members]
        if len(names) != len(set(names)) or 'receipt.json' not in names:
            raise ValueError('Duplicate or missing host LLVM cache entries')
        receipt_member = bundle.getmember('receipt.json')
        if not receipt_member.isfile() or receipt_member.size > 2 * 1024 * 1024:
            raise ValueError('Invalid host LLVM receipt')
        receipt = json.loads(bundle.extractfile(receipt_member).read())
        if receipt['schema'] != SCHEMA or set(names) != {'receipt.json', *receipt['files']}:
            raise ValueError('Host LLVM archive inventory differs from receipt')
        for name, info in receipt['files'].items():
            path = PurePosixPath(name)
            allowed = (len(path.parts) == 2 and path.parts[0] == 'bin' and path.name != 'llvm-config') or name.startswith('lib/clang/22/include/')
            if not allowed or path.is_absolute() or '..' in path.parts or '\\' in name:
                raise ValueError('Unsafe host LLVM cache path')
            member = bundle.getmember(name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if 'link' in info:
                if not member.issym() or info['link'] != 'llvm' or member.linkname != 'llvm' or path.parts[0] != 'bin':
                    raise ValueError('Invalid host LLVM alias')
                target.symlink_to('llvm')
            else:
                if not member.isfile():
                    raise ValueError('Host LLVM entry is not a regular file')
                with bundle.extractfile(member) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(info['mode'] & 0o755)
                if sha(target) != info['sha256']:
                    raise ValueError('Host LLVM file checksum mismatch')
        return receipt


def validate(args, prefix, receipt):
    validate_source(args.source)
    if receipt['llvmCommit'] != llvm_pin() or receipt['image'] != args.image:
        raise ValueError('Host LLVM pin or container image differs')
    if receipt['normalizedConfigure'] != normalized_config(args.config.read_text()):
        raise ValueError('Host LLVM configure inputs differ')
    if receipt['dynamicLibraries'] != dynamic_libraries(prefix / 'bin/llvm'):
        raise ValueError('Host LLVM runtime library bytes differ')
    if compiler_identity(prefix / 'bin/clang') != receipt['hostVersion']:
        raise ValueError('Host LLVM version differs')
    resource = Path(run([prefix / 'bin/clang', '-print-resource-dir'])).resolve()
    if resource != prefix / 'lib/clang/22':
        raise ValueError('Host LLVM resource headers did not relocate')
    for name in REQUIRED:
        if not (prefix / 'bin' / name).is_file():
            raise ValueError('Required host LLVM alias missing')
    with tempfile.TemporaryDirectory(prefix='.host-llvm-probe-', dir=prefix) as temporary:
        for target, machine in [('x86_64-w64-windows-gnu', b'\x64\x86'),
                                ('aarch64-w64-windows-gnu', b'\x64\xaa')]:
            output = Path(temporary) / 'probe.obj'
            subprocess.run([str(prefix / 'bin/clang++'), '-target', target, '-ffreestanding',
                            '-nostdinc', '-isystem', str(resource / 'include'), '-x', 'c++',
                            '-c', '-', '-o', str(output)],
                           input=b'#include <stddef.h>\n#include <stdint.h>\nstruct X { size_t n; }; int f(X x) { return int(x.n); }\n', check=True)
            if output.read_bytes()[:2] != machine:
                raise ValueError('Host LLVM emitted the wrong COFF machine')


def consume(args):
    with tempfile.TemporaryDirectory(prefix='host-llvm-import-') as temporary:
        staging = Path(temporary)
        receipt = unpack(args.archive, args.sha256, staging)
        validate(args, staging, receipt)
        if args.command == 'install':
            for name, info in receipt['files'].items():
                target = args.prefix / name
                if target.exists() or target.is_symlink():
                    same = (target.is_symlink() and os.readlink(target) == info.get('link')) if 'link' in info else (target.is_file() and not target.is_symlink() and sha(target) == info['sha256'])
                    if not same:
                        raise ValueError(f'Refusing to overwrite another compiler file: {target}')
            for name, info in receipt['files'].items():
                target = args.prefix / name
                if target.exists() or target.is_symlink():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if 'link' in info:
                    target.symlink_to(info['link'])
                else:
                    shutil.copy2(staging / name, target)
            # Probe the installed tools, permissions, runtime closure and header
            # discovery too; staging success alone is not installation proof.
            validate(args, args.prefix.resolve(), receipt)
            result = {'kind': 'imported-host-llvm', 'llvmCommit': llvm_pin(),
                      'archiveSha256': args.sha256, 'image': args.image,
                      'normalizedConfigure': receipt['normalizedConfigure'],
                      'hostCompilerSha256': receipt['files']['bin/llvm']['sha256'],
                      'coffTargetsVerified': ['x86_64', 'aarch64']}
            (args.prefix / 'host-llvm-cache-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'{args.command}: verified host LLVM cache {args.sha256}')


def prepare(args):
    consume(args)
    evidence = args.build / 'host-llvm-cache'
    evidence.mkdir(parents=True, exist_ok=True)
    snapshot = evidence / 'expected-config.txt'
    shutil.copy2(args.config, snapshot)
    common = [str(Path(__file__).resolve()), '--archive', str(args.archive.resolve()),
              '--source', str(args.source.resolve()), '--image', args.image,
              '--config', str(snapshot.resolve()), '--sha256', args.sha256]
    def quote(value):
        if any(char in value for char in ('$',';','\n','\r')):
            raise ValueError('Unsafe character in host LLVM CMake argument')
        return json.dumps(value)
    def command(verb, extra=()):
        return ' '.join(quote(x) for x in [sys.executable, common[0], verb, *common[1:], *extra])
    overlay = ('# Verified host compiler cache; target runtimes still build locally.\n'
               'ExternalProject_Add(llvm\n'
               '    SOURCE_DIR ${SOURCE_LOCATION}\n'
               '    DOWNLOAD_COMMAND "" UPDATE_COMMAND "" PATCH_COMMAND ""\n'
               '    CONFIGURE_COMMAND ""\n'
               f'    BUILD_COMMAND {command("validate")}\n'
               f'    INSTALL_COMMAND {command("install", ["--prefix", str(args.prefix.resolve())])}\n'
               '    LOG_BUILD 1 LOG_INSTALL 1\n)\n'
               'get_property(LLVM_SRC TARGET llvm PROPERTY _EP_SOURCE_DIR)\n')
    (args.winbuild / 'toolchain/llvm/llvm.cmake').write_text(overlay)
    print('Prepared explicit host LLVM cache validation/import steps; no donor stamps copied')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['export', 'validate', 'install', 'prepare'])
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--prefix', type=Path)
    parser.add_argument('--stamps', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--build', type=Path)
    parser.add_argument('--winbuild', type=Path)
    args = parser.parse_args()
    if args.command == 'export':
        if not args.prefix or not args.stamps:
            parser.error('export requires --prefix and --stamps')
        export(args)
    else:
        if not args.config or not re.fullmatch('[0-9a-f]{64}', args.sha256 or '') or (args.command == 'install' and not args.prefix):
            parser.error('consume requires --config, --sha256 and an install --prefix')
        if args.command == 'prepare':
            if not args.build or not args.winbuild or not args.prefix:
                parser.error('prepare requires --build, --winbuild and --prefix')
            prepare(args)
        else:
            consume(args)


if __name__ == '__main__':
    main()
