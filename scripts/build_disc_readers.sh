#!/usr/bin/env bash
# Build pinned optical disc readers into the Linux mpv prefix.
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
for name in ('libcdio', 'libcdio-paranoia', 'libdvdread', 'libdvdnav', 'libbluray_linux'):
    entry = components[name]
    if entry['kind'] != 'archive' or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
        raise ValueError(f'Expected a SHA-256 archive pin for {name}')
    print(name.removesuffix('_linux'), entry['version'], entry['url'], entry['sha256'])
PY
)
while read -r library version url digest; do
  name="$library-$version"
  archive="$sources/${url##*/}"
  tree="$sources/$name"
  curl --fail --silent --show-error --location --retry 2 --max-time 120 \
    --proto '=https,file' --output "$archive" "$url"
  printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
  tar --extract --file "$archive" --directory "$sources"
  case "$library" in
    libcdio|libcdio-paranoia)
      options=(--disable-shared --enable-static --disable-cxx --disable-example-progs)
      if [[ "$library" == libcdio ]]; then
        options+=(--disable-cddb --disable-vcd-info)
      fi
      (
        mkdir -p "$tree/build"
        cd "$tree/build"
        CFLAGS="${CFLAGS:--O2} -fPIC" ../configure --prefix="$prefix" --libdir="$prefix/lib" "${options[@]}"
        make -C lib -j"$jobs"
        make -C lib install
        make -C include install
        make install-pkgconfigDATA
      )
      ;;
    libdvdread) options=(-Dlibdvdcss=disabled) ;;
    libdvdnav) options=() ;;
    libbluray)
      options=(-Dbdj_jar=disabled -Denable_tools=false -Dfreetype=disabled -Dfontconfig=disabled -Dlibxml2=enabled)
      ;;
  esac
  notice="$prefix/share/licenses/pleazyng-codecs/$library"
  if [[ "$library" == libcdio* ]]; then
    install -Dm644 "$tree/AUTHORS" "$notice/AUTHORS"
  else
    meson setup "$tree/build" "$tree" --prefix="$prefix" --libdir=lib \
      --default-library=static --buildtype=release --wrap-mode=nodownload "${options[@]}"
    ninja -C "$tree/build" -j"$jobs" install
  fi
  install -Dm644 "$tree/COPYING" "$notice/COPYING"
  if [[ "$library" == libbluray ]]; then
    install -Dm644 "$tree/contrib/libudfread/COPYING" "$notice/COPYING.libudfread"
  fi
done <<< "$pins"
