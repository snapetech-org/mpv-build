#!/usr/bin/env python3
"""Link each shipped ELF against its packaged dependencies and public Android API stubs."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


TARGETS = {
    'armeabi-v7a': ('armv7a-linux-androideabi', 'arm-linux-androideabi'),
    'arm64-v8a': ('aarch64-linux-android', 'aarch64-linux-android'),
    'x86': ('i686-linux-android', 'i686-linux-android'),
    'x86_64': ('x86_64-linux-android', 'x86_64-linux-android'),
}


def check(directory, toolchain, abi, api):
    compiler, triple = TARGETS[abi]
    system = toolchain / 'sysroot/usr/lib' / triple / str(api)
    binaries = {path.name: path for path in directory.glob('*.so')}
    if not binaries or not system.is_dir():
        raise ValueError(f'Missing native libraries or Android {api} stubs for {abi}')
    dependencies = {}
    for name, path in binaries.items():
        dynamic = subprocess.check_output([toolchain / 'bin/llvm-readelf', '-dW', path], text=True)
        dependencies[name] = re.findall(r'Shared library: \[([^\]]+)\]', dynamic)

    with tempfile.TemporaryDirectory() as work:
        for name in sorted(binaries):
            # Only the object's own DT_NEEDED graph is visible. An unrelated
            # library in the AAR cannot satisfy an import just by being installed.
            pending = [name]
            linked = {}
            while pending:
                dependency = pending.pop()
                if dependency in linked:
                    continue
                path = binaries.get(dependency, system / dependency)
                if not path.is_file():
                    raise ValueError(f'{abi}/{name} requires unavailable {dependency} on Android {api}')
                linked[dependency] = path
                pending.extend(dependencies.get(dependency, ()))
            subprocess.run([
                toolchain / 'bin' / f'{compiler}{api}-clang',
                '-Wl,--no-as-needed,--no-allow-shlib-undefined',
                '-x', 'c', '-', '-x', 'none', *linked.values(), '-o', Path(work) / 'consumer',
            ], input='int main(void) { return 0; }\n', text=True, check=True)
    print(f'Checked {len(binaries)} shared libraries for {abi}, Android API {api}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('toolchain', type=Path)
    parser.add_argument('abi', choices=TARGETS)
    parser.add_argument('--api', type=int, default=25)
    args = parser.parse_args()
    check(args.directory, args.toolchain, args.abi, args.api)
