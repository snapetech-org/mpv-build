#!/usr/bin/env python3
"""Stage pinned compile-time QNN headers privately; never package the SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    'include/QNN/QnnInterface.h',
    'include/QNN/System/QnnSystemInterface.h',
    'include/QNN/HTP/QnnHtpPerfInfrastructure.h',
    'include/QNN/HTP/QnnHtpDevice.h',
)
NOTICES = ('LICENSE.pdf', 'NOTICE.txt', 'QNN_NOTICE.txt', 'QNN_TFLITE_DELEGATE_NOTICE.txt')


def sha256(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def extract_headers(archive, destination, pin):
    if sha256(archive) != pin['sha256']:
        raise ValueError('QAIRT archive does not match the pinned SHA-256')
    prefix = f"qairt/{pin['version']}/"
    files = {}
    with zipfile.ZipFile(archive) as sdk:
        for item in sdk.infolist():
            if not item.filename.startswith(prefix) or item.is_dir():
                continue
            relative = item.filename[len(prefix):]
            if not (relative.startswith('include/QNN/') or relative in NOTICES):
                continue
            parts = PurePosixPath(relative)
            if parts.is_absolute() or '..' in parts.parts or '\\' in relative:
                raise ValueError('Unsafe path in QAIRT header archive')
            if ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('SDK headers must be regular files')
            content = sdk.read(item)
            files[relative] = content
    if any(name not in files for name in REQUIRED + NOTICES):
        raise ValueError('QAIRT archive is missing required headers or licensing notices')
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    receipt = {'archiveSha256': pin['sha256'], 'version': pin['version'],
               'files': {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
    (destination / 'source.json').write_text(json.dumps(receipt, indent=2) + '\n')


def cache_valid(destination, pin):
    try:
        receipt = json.loads((destination / 'source.json').read_text())
        if receipt['archiveSha256'] != pin['sha256'] or receipt['version'] != pin['version']:
            return False
        files = receipt['files']
        return all(name in files for name in REQUIRED + NOTICES) and all(
            sha256(destination / name) == digest for name, digest in files.items())
    except (OSError, ValueError, KeyError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Reuse an existing official SDK archive after verification')
    parser.add_argument('--sdk-root', type=Path)
    args = parser.parse_args()
    pin = json.loads((ROOT / 'versions.json').read_text())['components']['qairt']
    # The vendor permits development use, but not standalone SDK distribution.
    # Keep headers outside the Android SDK directory uploaded to public caches.
    private_root = Path(os.environ.get('RUNNER_TEMP', ROOT / 'build' / 'private-sdk'))
    destination = args.sdk_root or private_root / 'qairt' / pin['version']
    if not cache_valid(destination, pin):
        if args.archive:
            extract_headers(args.archive, destination, pin)
        else:
            private_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='qairt-download-', dir=private_root) as work:
                archive = Path(work) / 'sdk.zip'
                with urllib.request.urlopen(pin['url'], timeout=60) as response, archive.open('wb') as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                extract_headers(archive, destination, pin)
    print(destination.resolve())


if __name__ == '__main__':
    main()
