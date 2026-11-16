#!/usr/bin/env bash
# Build a pinned standalone decoder for the ABI selected by build.sh.
set -euo pipefail

. ../../include/path.sh

action=${1:?action}
component=${2:?component}
build_dir="pleazyng-build-${prefix_name}"

if [[ "$action" == clean ]]; then
	rm -rf "$build_dir"
	if [[ "$component" == davs2 ]]; then
		rm -rf "../.pleazyng-davs2-build-${prefix_name}"
	fi
	exit 0
fi
if [[ "$action" != build ]]; then
	echo >&2 "Unsupported decoder action: $action"
	exit 2
fi

case "$component" in
	xevd)
		options=(-DSET_PROF=MAIN)
		if [[ "$prefix_name" == arm64-v8a ]]; then
			options+=(-DARM=TRUE)
		fi

		;;
	davs2)
		# davs2 uses its own configure/Makefile build, not CMake.
		options=()
		;;
	lcevc_dec)
		options=(-DANDROID_STL=c++_shared)
		;;
	uavs3d)
		options=(-DCOMPILE_10BIT=ON)
		;;
	*)
		echo >&2 "Unsupported Android video decoder: $component"
		exit 2
		;;
esac

toolchain_file="$ANDROID_HOME/ndk/$v_ndk/build/cmake/android.toolchain.cmake"
if [[ ! -f "$toolchain_file" ]]; then
	echo >&2 "Android NDK toolchain is missing: $toolchain_file"
	exit 1
fi

export BUILD_SUFFIX="-$prefix_name"
export ANDROID_ABI="$prefix_name"
export CMAKE_INSTALL_PREFIX=/usr/local
export DESTDIR="$prefix_dir"

if [[ "$component" == davs2 ]]; then
	../../../../scripts/build_video_decoder.sh \
		"$component" "$PWD" "$prefix_dir" "$cores"
else
	../../../../scripts/build_video_decoder.sh \
		"$component" "$PWD" "$prefix_dir" "$cores" \
		-DCMAKE_TOOLCHAIN_FILE="$toolchain_file" \
		-DANDROID_ABI="$prefix_name" \
		-DANDROID_PLATFORM=android-25 \
		"${options[@]}"
fi
