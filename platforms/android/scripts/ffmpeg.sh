#!/usr/bin/env bash
set -euo pipefail

. ../../include/path.sh

if [ "$1" = "build" ]; then
	true
elif [ "$1" = "clean" ]; then
	rm -rf _build$ndk_suffix
	exit 0
else
	exit 255
fi

mkdir -p _build$ndk_suffix
cd _build$ndk_suffix

cpu=armv7-a
[[ "$ndk_triple" == "aarch64"* ]] && cpu=armv8-a
[[ "$ndk_triple" == "x86_64"* ]] && cpu=generic
[[ "$ndk_triple" == "i686"* ]] && cpu="i686 --disable-asm"

cpuflags=
[[ "$ndk_triple" == "arm"* ]] && cpuflags="$cpuflags -mfpu=neon -mcpu=cortex-a8"

../configure \
	--target-os=android --enable-cross-compile --cross-prefix=$ndk_triple- --cc=$CC \
	--arch=${ndk_triple%%-*} --cpu=$cpu --pkg-config=pkg-config --pkg-config-flags=--static --nm=llvm-nm \
	--extra-cflags="-I$prefix_dir/include $cpuflags" --extra-ldflags="-L$prefix_dir/lib" \
	--extra-libs="-ldovi -lc++_shared -llog" \
	--enable-{jni,mediacodec,openssl,libdav1d,libdav2d,libdovi,libxevd,libuavs3d,libdavs2,liblcevc-dec,libxml2,libjxl} --disable-vulkan \
	--disable-static --enable-shared --enable-{gpl,version3} \
	--disable-{stripping,doc,programs} \
	--enable-{decoders,demuxers,parsers,bsfs} \
	--disable-{muxers,encoders,devices,filters} \
	--enable-muxer=spdif,mpegts,matroska \
	--enable-filter=adelay,amix,asetpts,atrim,aecho,aformat,aresample,asetrate,aspectralstats,atempo,bass,equalizer,stereowiden,treble,volume,bwdif,decimate,fieldmatch,loudnorm,acompressor,alimiter \
	--disable-v4l2-m2m

make -j$cores
make DESTDIR="$prefix_dir" install
