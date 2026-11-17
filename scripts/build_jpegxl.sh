#!/usr/bin/env bash
# Build the reviewed JPEG XL source and its exact codec dependencies.
set -euo pipefail

source_dir=$(realpath "${1:?source directory}")
prefix=$(realpath "${2:?install prefix}")
jobs=${3:-4}
shift 3
build="$source_dir/pleazyng-build${BUILD_SUFFIX:-}"
install_prefix=${CMAKE_INSTALL_PREFIX:-$prefix}
dependencies=(brotli highway lcms)
paths=()
for dependency in "${dependencies[@]}"; do paths+=("third_party/$dependency"); done
git -C "$source_dir" submodule update --init --depth 1 --jobs 3 -- "${paths[@]}"
for path in "${paths[@]}"; do
  expected=$(git -C "$source_dir" rev-parse "HEAD:$path")
  actual=$(git -C "$source_dir/$path" rev-parse HEAD)
  if [[ "$actual" != "$expected" ]]; then
    echo "JPEG XL dependency $path: expected $expected, found $actual" >&2
    exit 1
  fi
done

cmake -S "$source_dir" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_INSTALL_PREFIX="$install_prefix" -DCMAKE_INSTALL_LIBDIR=lib \
  -DBUILD_SHARED_LIBS=OFF -DBUILD_TESTING=OFF \
  -DJPEGXL_ENABLE_TOOLS=OFF -DJPEGXL_ENABLE_JPEGLI=OFF -DJPEGXL_ENABLE_MANPAGES=OFF \
  -DJPEGXL_ENABLE_BENCHMARK=OFF -DJPEGXL_ENABLE_EXAMPLES=OFF -DJPEGXL_ENABLE_JNI=OFF \
  -DJPEGXL_ENABLE_SJPEG=OFF -DJPEGXL_ENABLE_SKCMS=OFF -DJPEGXL_ENABLE_TRANSCODE_JPEG=OFF "$@"
cmake --build "$build" --parallel "$jobs"
cmake --install "$build"

# The static CMS archive depends on the bundled Little CMS target, which
# upstream's install does not export. Give it a private linker name and
# leave the host's independently installed liblcms2 untouched.
install -m 644 "$build/third_party/liblcms2.a" "$prefix/lib/libjxl_lcms2.a"
python3 - "$prefix" "$source_dir" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

prefix, source = map(Path, sys.argv[1:])
pcs = prefix / 'lib/pkgconfig'
for name in ('libjxl', 'libjxl_cms', 'libjxl_threads'):
    path = pcs / (name + '.pc')
    data = path.read_text()
    if os.environ.get('ANDROID_ABI'):
        data = re.sub(r'(?<!\S)-l(?:stdc\+\+|c\+\+)(?!\S)', '', data)
    if name == 'libjxl_cms':
        data, count = re.subn(r'^Libs.private:', 'Libs.private: -ljxl_lcms2 -lhwy', data, flags=re.M)
        if count != 1:
            raise ValueError('Expected one static JPEG XL CMS link field')
    path.write_text(data)
notices = prefix / 'share/licenses/pleazyng-codecs/libjxl'
notices.mkdir(parents=True, exist_ok=True)
files = {}
for name, original in {
    'LICENSE': source / 'LICENSE',
    'PATENTS': source / 'PATENTS',
    'LICENSE.brotli': source / 'third_party/brotli/LICENSE',
    'LICENSE.highway': source / 'third_party/highway/LICENSE',
    'LICENSE.lcms': source / 'third_party/lcms/LICENSE',
}.items():
    shutil.copyfile(original, notices / name)
    files[name] = hashlib.sha256(original.read_bytes()).hexdigest()
(notices / 'notice-manifest.json').write_text(json.dumps({'files': files}, sort_keys=True, indent=2) + '\n')
PY
