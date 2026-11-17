#!/usr/bin/env bash
# Build a verified source checkout into the private FFmpeg prefix. Callers own
# acquisition and hash verification; this script never fetches moving sources.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
  libxml2)
    cmake -S "$source_dir" -B "$build" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_INSTALL_PREFIX="$install_prefix" -DCMAKE_INSTALL_LIBDIR=lib \
      -DBUILD_SHARED_LIBS=OFF -DLIBXML2_WITH_PROGRAMS=OFF -DLIBXML2_WITH_TESTS=OFF \
      -DLIBXML2_WITH_ICONV=OFF -DLIBXML2_WITH_ICU=OFF -DLIBXML2_WITH_MODULES=OFF "$@"
    cmake --build "$build" --parallel "$jobs"
    cmake --install "$build"
    # The native package already carries this notice directory intact.
    install -Dm644 "$source_dir/Copyright" "$prefix/share/licenses/pleazyng-codecs/libxml2/Copyright"
    exit 0
    ;;
  lcevc_dec)
    cmake -S "$source_dir" -B "$build" -G Ninja \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DCMAKE_INSTALL_PREFIX="$install_prefix" -DCMAKE_INSTALL_LIBDIR=lib \
      -DBUILD_SHARED_LIBS=OFF -DVN_SDK_SYSTEM_INSTALL=OFF \
      -DVN_SDK_API_LAYER=ON -DVN_SDK_PIPELINE=ON -DVN_SDK_PIPELINE_CPU=ON \
      -DVN_SDK_PIPELINE_VULKAN=OFF -DVN_SDK_PIXEL_PROCESSING=ON \
      -DVN_SDK_EXECUTABLES=OFF -DVN_SDK_UNIT_TESTS=OFF \
      -DVN_SDK_SAMPLE_SOURCE=OFF -DVN_SDK_JSON_CONFIG=OFF -DVN_SDK_DOCS=OFF \
      -DVN_SDK_BUILD_DETAILS=OFF -DVN_SDK_TRACING=OFF -DVN_SDK_METRICS=OFF "$@"
    cmake --build "$build" --parallel "$jobs"
    cmake --install "$build"
    runtime=${LCEVC_CXX_RUNTIME:-stdc++}
    [[ -z "${ANDROID_ABI:-}" ]] || runtime=c++_shared
    python3 "$SCRIPT_DIR/fix_lcevc_pkgconfig.py" \
      "$prefix/lib/pkgconfig/lcevc_dec.pc" --runtime "$runtime"
    ;;
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
    davs2_source=$source_dir
    if [[ -n "${ANDROID_ABI:-}" ]]; then
      # davs2 configures in its source checkout. Keep each Android ABI isolated
      # so generated headers and object files can never cross-contaminate.
      davs2_source="$source_dir/../.pleazyng-davs2-build-${ANDROID_ABI}"
      rm -rf "$davs2_source"
      mkdir -p "$davs2_source"
      cp -a "$source_dir/." "$davs2_source/"
      rm -rf "$davs2_source/.git"
    fi
    cd "$davs2_source/build/linux"
    # Generic C++ is available on both Linux architectures; this avoids x86-only
    # assembler assumptions in the portable decoder floor.
    configure_args=(--prefix="$install_prefix" --enable-pic --disable-cli --disable-asm)
    if [[ -n "${ANDROID_ABI:-}" ]]; then
      case "$ANDROID_ABI" in
        arm64-v8a) target_host=aarch64-linux-gnu ;;
        armeabi-v7a) target_host=arm-linux-gnueabi ;;
        x86) target_host=i686-linux-gnu ;;
        x86_64) target_host=x86_64-linux-gnu ;;
        *) echo "Unsupported Android ABI for davs2: $ANDROID_ABI" >&2; exit 2 ;;
      esac
      configure_args+=(--host="$target_host")
    else
      configure_args=(--prefix="$prefix" --enable-pic --disable-cli --disable-asm "$@")
    fi
    CC="${CXX:-g++}" ./configure "${configure_args[@]}" --bit-depth=10
    sed -i -E 's/(#define XBUILD_TIME[[:space:]]+)"[^"]*"/\1"2020-01-01 00:00:00"/' "$davs2_source/source/version.h"
    make -j"$jobs"
    make install
    # Upstream 1.7's shallow checkout emits the invalid pkg-config version
    # "1.6.". Preserve its advertised API floor with an explicit patch zero.
    sed -i -E 's/^Version: ([0-9]+\.[0-9]+)\.$/Version: \1.0/' "$prefix/lib/pkgconfig/davs2.pc"
    if [[ -n "${ANDROID_ABI:-}" ]]; then
      # Bionic provides pthreads through libc; do not emit a separate archive
      # dependency in the pkg-config metadata consumed by FFmpeg.
      sed -i 's/ -lpthread//g' "$prefix/lib/pkgconfig/davs2.pc"
    fi
    ;;
  *) echo "Unsupported decoder component: $component" >&2; exit 2 ;;
esac

python3 "$SCRIPT_DIR/stage_decoder_notices.py" "$source_dir" "$prefix" "$component"
