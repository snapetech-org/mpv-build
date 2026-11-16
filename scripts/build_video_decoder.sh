#!/usr/bin/env bash
# Build a verified source checkout into the private FFmpeg prefix. Callers own
# acquisition and hash verification; this script never fetches moving sources.
set -euo pipefail
component=${1:?component}
source_dir=${2:?source directory}
prefix=${3:?install prefix}
jobs=${4:-4}
shift 4
source_dir=$(realpath "$source_dir")
mkdir -p "$prefix/lib/pkgconfig" "$prefix/include"
prefix=$(realpath "$prefix")
build="$source_dir/pleazyng-build${BUILD_SUFFIX:-}"
install_prefix=${CMAKE_INSTALL_PREFIX:-$prefix}
pthread_libs='-lpthread'
if [[ -n "${ANDROID_ABI:-}" ]]; then
  # Android's pthread API is part of libc rather than a separate archive.
  pthread_libs=''
fi

case "$component" in
  xevd)
    cmake -S "$source_dir" -B "$build" -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_INSTALL_PREFIX="$install_prefix" -DCMAKE_INSTALL_LIBDIR=lib -DSET_PROF=MAIN "$@"
    cmake --build "$build" --target xevd --parallel "$jobs"
    # Upstream's install also installs a shared-library symlink. Stage only
    # the static API so the released libmpv has no accidental shared dependency.
    install -m 644 "$build/src_main/libxevd.a" "$prefix/lib/libxevd.a"
    install -m 644 "$source_dir/inc/xevd.h" "$build/xevd_exports.h" "$prefix/include/"
    cat > "$prefix/lib/pkgconfig/xevd.pc" <<EOF
prefix=$install_prefix
libdir=\${prefix}/lib
includedir=\${prefix}/include
Name: xevd
Description: MPEG-5 EVC decoder (Main and Baseline)
Version: 0.8.0
Libs: -L\${libdir} -lxevd
Libs.private: -lm $pthread_libs
Cflags: -I\${includedir}
EOF
    ;;
  uavs3d)
    cmake -S "$source_dir" -B "$build" -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_INSTALL_PREFIX="$install_prefix" -DBUILD_SHARED_LIBS=OFF -DCOMPILE_10BIT=ON "$@"
    cmake --build "$build" --target uavs3d --parallel "$jobs"
    if [[ -n "${DESTDIR:-}" ]]; then
      DESTDIR="$DESTDIR" cmake --install "$build"
    else
      cmake --install "$build"
    fi
    if [[ -n "${ANDROID_ABI:-}" ]]; then
      # Android's pthread API is part of libc, not a separate -lpthread
      # archive. The static library's pthread calls resolve from Bionic.
      sed -i 's/ -lpthread//g' "$prefix/lib/pkgconfig/uavs3d.pc"
    fi
    ;;
  davs2)
    cd "$source_dir/build/linux"
    # The pinned release rejects --bit-depth=10. Do not claim 10-bit AVS2.
    # Generic C++ is available on both Linux architectures; this avoids x86-only
    # assembler assumptions in the portable decoder floor.
    CC="${CXX:-g++}" ./configure --prefix="$prefix" --enable-pic --disable-cli --disable-asm "$@"
    sed -i -E 's/(#define XBUILD_TIME[[:space:]]+)"[^"]*"/\1"2020-01-01 00:00:00"/' "$source_dir/source/version.h"
    make -j"$jobs"
    make install
    # Upstream 1.7's shallow checkout emits the invalid pkg-config version
    # "1.6.". Preserve its advertised API floor with an explicit patch zero.
    sed -i -E 's/^Version: ([0-9]+\.[0-9]+)\.$/Version: \1.0/' "$prefix/lib/pkgconfig/davs2.pc"
    ;;
  *) echo "Unsupported decoder component: $component" >&2; exit 2 ;;
esac
