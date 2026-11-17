#!/usr/bin/env bash
# Build pinned DVD and Blu-ray title readers into the Linux mpv prefix.
set -euo pipefail

manifest=${1:?version manifest}
sources=$2
prefix=$3
jobs=$4
pins=$(python3 - "$manifest" <<'PY'
import json
import re
import sys

components = json.load(open(sys.argv[1], encoding='utf-8'))['components']
for name in ('libdvdread', 'libdvdnav', 'libbluray_linux'):
    entry = components[name]
    if entry['kind'] != 'archive' or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
        raise ValueError(f'Expected a SHA-256 archive pin for {name}')
    print(name.removesuffix('_linux'), entry['version'], entry['url'], entry['sha256'])
PY
)
while read -r library version url digest; do
  name="$library-$version"
  archive="$sources/$name.tar.xz"
  tree="$sources/$name"
  curl --fail --silent --show-error --location --retry 2 --max-time 120 \
    --proto '=https,file' --output "$archive" "$url"
  printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
  tar --extract --xz --file "$archive" --directory "$sources"
  case "$library" in
    libdvdread) options=(-Dlibdvdcss=disabled) ;;
    libdvdnav) options=() ;;
    libbluray)
      options=(-Dbdj_jar=disabled -Denable_tools=false -Dfreetype=disabled -Dfontconfig=disabled -Dlibxml2=enabled)
      ;;
  esac
  meson setup "$tree/build" "$tree" --prefix="$prefix" --libdir=lib \
    --default-library=static --buildtype=release --wrap-mode=nodownload "${options[@]}"
  ninja -C "$tree/build" -j"$jobs" install
  notice="$prefix/share/licenses/pleazyng-codecs/$library"
  install -Dm644 "$tree/COPYING" "$notice/COPYING"
  if [[ "$library" == libbluray ]]; then
    install -Dm644 "$tree/contrib/libudfread/COPYING" "$notice/COPYING.libudfread"
  fi
done <<< "$pins"
