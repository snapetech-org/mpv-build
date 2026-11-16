#!/usr/bin/env python3
"""Keep LCEVC's static runtime dependencies after the archives that use them."""
import argparse
from pathlib import Path
import re

RUNTIME = re.compile(r'(?<!\S)(?:-l(?:stdc\+\+|c\+\+(?:_shared|abi)?|m|pthread|log|dl|atomic)|-pthread)(?=\s|$)')


def normalize(text: str, runtime: str) -> str:
    if runtime not in {'stdc++', 'c++', 'c++_shared'}:
        raise ValueError('Unsupported C++ runtime')
    lines = text.splitlines()
    matches = [i for i, line in enumerate(lines) if line.startswith('Libs:')]
    if len(matches) != 1 or '-llcevc_dec_api' not in lines[matches[0]]:
        raise ValueError('Expected one static LCEVC API library list')
    index = matches[0]
    libraries = lines[index][len('Libs:'):].strip()
    dependencies = list(dict.fromkeys(RUNTIME.findall(libraries)))
    dependencies = [value for value in dependencies if not value.startswith(('-lstdc++', '-lc++'))]
    if runtime == 'c++_shared':
        dependencies = [value for value in dependencies if value != '-lpthread']
    archives = RUNTIME.sub('', libraries)
    lines[index] = 'Libs: ' + re.sub(r'\s+', ' ', archives).strip() + ' ' + ' '.join([f'-l{runtime}', *dependencies])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--runtime', choices=('stdc++', 'c++', 'c++_shared'), required=True)
    args = parser.parse_args()
    args.path.write_text(normalize(args.path.read_text(), args.runtime))


if __name__ == '__main__':
    main()
