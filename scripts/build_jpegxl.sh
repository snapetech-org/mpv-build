#!/usr/bin/env bash
# Build the reviewed JPEG XL source and its exact codec dependencies.
set -euo pipefail

source_dir=$(realpath "${1:?source directory}")
prefix=$(realpath "${2:?install prefix}")
jobs=${3:-4}
shift 3
build="$source_dir/pleazyng-build${BUILD_SUFFIX:-}"
install_prefix=${CMAKE_INSTALL_PREFIX:-$prefix}
dependencies=(brotli highway)
if [[ -n ${JXL_LCMS2_PREFIX:-} ]]; then
  # Apple already ships Little CMS as a separate SwiftPM binary target.
  test -s "$JXL_LCMS2_PREFIX/lib/liblcms2.a"
  test -s "$JXL_LCMS2_PREFIX/include/lcms2.h"
  set -- "$@" -DJPEGXL_FORCE_SYSTEM_LCMS2=ON \
    "-DLCMS2_LIBRARY=$JXL_LCMS2_PREFIX/lib/liblcms2.a" "-DLCMS2_INCLUDE_DIR=$JXL_LCMS2_PREFIX/include"
else
  dependencies+=(lcms)
fi
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
if [[ -z ${JXL_LCMS2_PREFIX:-} ]]; then
  install -m 644 "$build/third_party/liblcms2.a" "$prefix/lib/libjxl_lcms2.a"
fi
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
        private = '-lhwy' if os.environ.get('JXL_LCMS2_PREFIX') else '-ljxl_lcms2 -lhwy'
        data, count = re.subn(r'^Libs.private:', 'Libs.private: ' + private, data, flags=re.M)
        if count != 1:
            raise ValueError('Expected one static JPEG XL CMS link field')
    path.write_text(data)
notices = prefix / 'share/licenses/pleazyng-codecs/libjxl'
notices.mkdir(parents=True, exist_ok=True)
files = {}
originals = {
    'LICENSE': source / 'LICENSE',
    'PATENTS': source / 'PATENTS',
    'LICENSE.brotli': source / 'third_party/brotli/LICENSE',
    'LICENSE.highway': source / 'third_party/highway/LICENSE',
}
if not os.environ.get('JXL_LCMS2_PREFIX'):
    originals['LICENSE.lcms'] = source / 'third_party/lcms/LICENSE'
for name, original in originals.items():
    shutil.copyfile(original, notices / name)
    files[name] = hashlib.sha256(original.read_bytes()).hexdigest()
(notices / 'notice-manifest.json').write_text(json.dumps({'files': files}, sort_keys=True, indent=2) + '\n')
PY
