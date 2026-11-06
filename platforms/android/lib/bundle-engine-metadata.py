#!/usr/bin/env python3
"""Include exact FFmpeg headers and engine provenance in the normal AAR."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

ABIS = ('arm64-v8a', 'armeabi-v7a', 'x86', 'x86_64')
PREFIX = 'META-INF/plezyng-dv/ffmpeg-headers/'
ENGINE = 'plezyng-dv-fel-v1'
ROOT = Path(__file__).resolve().parents[3]


def bundle(aar: Path, natives: Path):
    versions = json.loads((ROOT / 'versions.json').read_text())['components']
    def pin(name):
        entry = versions[name]
        return (entry.get('overrides') or {}).get('android', entry)
    if pin('mpv').get('patchSet') != 'fel':
        raise ValueError('normal Android engine must include the FEL implementation')
    trees = {}
    for abi in ABIS:
        include = natives / abi / 'include'
        headers = {str(p.relative_to(include)): p.read_bytes()
                   for component in ('libavcodec', 'libavformat', 'libavutil', 'libswresample', 'libswscale')
                   for p in (include / component).glob('*.h')}
        for required in ('libavcodec/avcodec.h', 'libavcodec/mediacodec.h',
                         'libavutil/avconfig.h', 'libswresample/swresample.h'):
            if required not in headers:
                raise ValueError(f'{abi}: missing matching installed header {required}')
        trees[abi] = headers
    reference = trees[ABIS[0]]
    # avconfig.h is generated for the target architecture (including
    # AV_HAVE_FAST_UNALIGNED). Preserve each ABI's value instead of applying
    # one architecture's inline-code assumptions to all Media3 JNI builds.
    for abi, headers in trees.items():
        if set(headers) != set(reference) or any(headers[name] != reference[name]
             for name in reference if name != 'libavutil/avconfig.h'):
            raise ValueError(f'{abi}: non-generated FFmpeg headers differ from the source pin')
    metadata = {
        'schema_version': 2, 'engine_id': ENGINE, 'abis': list(ABIS),
        'ffmpeg_commit': pin('ffmpeg')['commit'], 'mpv_commit': pin('mpv')['commit'],
        'libplacebo_commit': pin('libplacebo')['commit'], 'ffmpeg_headers': PREFIX,
        'activation': 'runtime-settings-default-off', 'qualification': 'unqualified',
        'header_sha256': {abi: {name: hashlib.sha256(data).hexdigest() for name, data in sorted(headers.items())}
                          for abi, headers in trees.items()},
    }
    with tempfile.TemporaryDirectory(dir=aar.parent) as temporary:
        output = Path(temporary) / 'bundled.aar'
        with zipfile.ZipFile(aar) as source, zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            for abi in ABIS:
                data = source.read(f'jni/{abi}/libmpv.so')
                if ENGINE.encode() not in data:
                    raise ValueError(f'{abi}: AAR lacks the compiled experimental engine identity')
            for entry in source.infolist():
                if entry.filename == 'META-INF/plezyng-dv-engine.json' or entry.filename.startswith(PREFIX):
                    raise ValueError('AAR already contains DV metadata; refuse to overwrite it')
                target.writestr(entry, source.read(entry))
            def write(name, data):
                entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                target.writestr(entry, data)
            write('META-INF/plezyng-dv-engine.json', (json.dumps(metadata, sort_keys=True, indent=2) + '\n').encode())
            for abi, headers in trees.items():
                for name, data in sorted(headers.items()):
                    write(PREFIX + abi + '/' + name, data)
        output.replace(aar)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('aar', type=Path)
    parser.add_argument('natives', type=Path)
    args = parser.parse_args()
    bundle(args.aar, args.natives)
