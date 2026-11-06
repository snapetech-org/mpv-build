#!/usr/bin/env python3
"""Keep a trusted Windows compiler cache at its original workspace path.

Hosted workers can reuse the private Ubuntu toolchain without regenerating its
absolute-path build graph. This creates only the known legacy workspace alias
on a disposable hosted worker; it never rewrites cache contents or a JIT host.
"""
from pathlib import Path
import argparse
import os
import subprocess

LEGACY = Path('/opt/actions-runner/_work/mpv-build/mpv-build')
SUFFIX = '/build/windows/mpv-winbuild-cmake'


def cached_root(cache: Path) -> Path | None:
    if not cache.exists():
        return None
    for line in cache.read_text().splitlines():
        if line.startswith('CMAKE_HOME_DIRECTORY:INTERNAL='):
            source = line.split('=', 1)[1]
            if not source.endswith(SUFFIX):
                raise ValueError('restored CMake source does not belong to the Windows producer')
            return Path(source[:-len(SUFFIX)])
    raise ValueError('restored Windows cache has no source workspace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arch', choices=('x86_64', 'aarch64'))
    args = parser.parse_args()
    workspace = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    old = cached_root(workspace / f'build/windows/{args.arch}/CMakeCache.txt')
    selected = workspace
    if old is not None and old != workspace:
        if old != LEGACY:
            raise ValueError(f'unrecognized cached workspace: {old}')
        if old.exists() or old.is_symlink():
            if old.resolve() != workspace:
                raise ValueError('legacy workspace path is occupied; refusing to replace it')
        else:
            subprocess.run(['sudo', 'mkdir', '-p', str(old.parent)], check=True)
            subprocess.run(['sudo', 'ln', '-s', str(workspace), str(old)], check=True)
        selected = old
    with open(os.environ['GITHUB_ENV'], 'a') as output:
        output.write(f'MPV_WINDOWS_WORKSPACE={selected}\n')
    print(f'Validated compiler-cache workspace: {selected}')


if __name__ == '__main__':
    main()
