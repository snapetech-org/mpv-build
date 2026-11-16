#!/usr/bin/env bash
# Builds the mpv-android AAR (README.md, Android library) from four libmpv-android tarballs and leaves it as
# dist/release/mpv-android.aar, the unkeyed name `keys.py record-packages` renames to the group.json
# assetPattern's content-addressed one, with the debug files of its native libraries beside it as
# dist/release/mpv-android-<abi>-symbols.zip (renamed the same way, after symbolsPattern). Tarballs whose libraries
# carry no GNU build-id (a key published before platforms/android/include/loadarch.sh linked with one) fail there.
#
# Usage: build-aar.sh [--tarballs <dir> | --key <key>] [-- <more Gradle tasks or flags>]
#   (none)           the tarballs artifacts.json pins at this checkout, fetched from binaries-android and checked
#                    against the recorded sha256 (fetch-tarballs.py)
#   --key <key>      the published tarballs of any libmpv-android content key, checked against the sha256 GitHub
#                    records for each asset
#   --tarballs <dir> local tarballs, e.g. dist/release after package.sh (libmpv-android-<abi>.tar.gz) or a
#                    directory of published ones (libmpv-android-<key>-<abi>.tar.gz)
#   -- <args>        passed to Gradle after assembleRelease (CI adds testDebugUnitTest assembleDebugAndroidTest)
# Needs JDK 17 or newer and an Android SDK (ANDROID_HOME, or sdk.dir in platforms/android/lib/local.properties);
# Gradle installs the NDK toolchain/android.txt pins and CMake 4.1.2 when the SDK lacks them. The symbols take
# python3, unzip, zip and that NDK's llvm-objcopy.
set -euo pipefail

# Fail before Gradle if symbol packaging cannot complete on this host.
for tool in python3 java zip unzip tar find sort; do
	command -v "$tool" >/dev/null || { echo "build-aar.sh: missing required tool: $tool" >&2; exit 1; }
done

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../../.." && pwd)"

tarballs=
key=
extra=()
while [ $# -gt 0 ]; do
	case "$1" in
		--tarballs) shift; tarballs=$1 ;;
		--key) shift; key=$1 ;;
		--) shift; extra=("$@"); break ;;
		*) sed -n '2,18p' "$0" >&2; exit 2 ;;
	esac
	shift
done
if [ -n "$tarballs" ] && [ -n "$key" ]; then
	echo "build-aar.sh: --tarballs and --key are exclusive" >&2
	exit 2
fi

if [ -z "$tarballs" ]; then
	tarballs="$(python3 "$here/fetch-tarballs.py" ${key:+--key "$key"})"
fi
tarballs="$(cd "$tarballs" && pwd)"

# ${extra[@]+...}: macOS's bash 3.2 calls an empty array unbound under set -u.
(cd "$here" && ./gradlew --stacktrace "-Pmpv.tarballs=$tarballs" assembleRelease ${extra[@]+"${extra[@]}"})

# The debug files: one zip per ABI of the AAR, holding a debug file for each jni/<abi>/*.so it ships, under the
# same name. AGP strips the AAR's copies; the unstripped twin of each (the same GNU build-id, symbols kept) is
# the tarball's (build/mpv/<abi>/lib), CMake's libplayer.so in Gradle's intermediates, or for libc++_shared.so
# the NDK's. `symbols.py match` picks it by that id, so a stale intermediate or another ABI's copy is never
# taken, llvm-objcopy --only-keep-debug cuts it to its symbols and DWARF, and `symbols.py pack` checks the id
# once more. A library of ours without an id or a debug file fails the build: its crashes could never be
# symbolicated. libc++_shared.so is not ours and is left out when the NDK has no copy with its id.
aar="$here/build/outputs/aar/mpv-android-release.aar"
symbols="$root/scripts/symbols.py"
ndk_version="$(sed -n 's/^ndk=//p' "$root/toolchain/android.txt")"
# The SDK Gradle used: sdk.dir (a Java properties value, hence the unescaping) over ANDROID_HOME.
sdk=
if [ -f "$here/local.properties" ]; then
	sdk="$(sed -n 's/^sdk\.dir[[:space:]]*[=:][[:space:]]*//p' "$here/local.properties" | sed 's/\\\(.\)/\1/g')"
fi
sdk="${sdk:-${ANDROID_HOME:-}}"
toolchain="$(echo "$sdk/ndk/$ndk_version/toolchains/llvm/prebuilt/"*)"
objcopy="$toolchain/bin/llvm-objcopy"
if [ ! -x "$objcopy" ]; then
	echo "build-aar.sh: no llvm-objcopy in the pinned NDK $ndk_version of the SDK at '$sdk'" >&2
	exit 1
fi

# The files that may be <abi>/<name> unstripped, sorted: the tarball's, every copy in Gradle's intermediates
# (CMake leaves libplayer.so there) and, for libc++_shared.so, the NDK's, which sits under a target triple rather
# than an ABI, so every triple's copy goes in and the id picks this ABI's. (A function: macOS's bash 3.2 misparses
# a comment with an apostrophe inside a process substitution.)
debug_candidates () {
	{
		find "$here/build/mpv/$1/lib" "$here/build/intermediates" -type f -path "*/$1/*" -name "$2"
		if [ "$2" = libc++_shared.so ]; then
			find "$toolchain/sysroot/usr/lib" -type f -name "$2"
		fi
	} | LC_ALL=C sort
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
unzip -q "$aar" 'jni/*' -d "$work/aar"

# AARs are redistributed independently of the native tarballs. Carry every
# decoder notice into the AAR and require all ABI packages to agree on the
# same license tree, so one ABI's complete copy cannot hide a missing notice.
license_stage="$work/license-stage"
mkdir -p "$license_stage/META-INF/licenses"
python3 - "$tarballs" "$license_stage/META-INF/licenses" "$aar" <<'PY'
import pathlib
import re
import stat
import sys
import tarfile
import zipfile

root = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
aar = pathlib.Path(sys.argv[3])
abis = ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
expected = None
for abi in abis:
    pattern = re.compile(r"libmpv-android-(?:[0-9a-f]{12}-)?" + re.escape(abi) + r"\.tar\.gz\Z")
    archives = sorted(path for path in root.iterdir() if pattern.fullmatch(path.name))
    if len(archives) != 1:
        raise SystemExit(f"expected one Android native tarball for {abi}, found {[p.name for p in archives]}")
    with tarfile.open(archives[0], "r:gz") as archive:
        files = {}
        for member in archive.getmembers():
            notice_root = "share/licenses/pleazyng-codecs/"
            if not member.name.startswith(notice_root):
                continue
            if "\\" in member.name or "\0" in member.name:
                raise SystemExit(f"unsafe license archive member: {member.name!r}")
            relative = pathlib.PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"unsafe license archive member: {member.name}")
            if member.isdir():
                continue
            if not member.isfile():
                raise SystemExit(f"unsupported license archive member: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"cannot read license archive member: {member.name}")
            files[str(relative.relative_to(notice_root))] = source.read()
    if not files:
        raise SystemExit(f"{archives[0].name}: no license files in native package")
    if expected is None:
        expected = files
    elif files != expected:
        raise SystemExit(f"{archives[0].name}: license files differ from the first ABI package")

for relative, content in sorted(expected.items()):
    output = destination / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)

# Append normalized entries in a stable order with fixed timestamps and modes.
# This keeps the AAR reproducible across rebuilds even though the package is
# augmented after Gradle assembles it.
with zipfile.ZipFile(aar, "r") as package:
    if any(name.startswith("META-INF/licenses/") for name in package.namelist()):
        raise SystemExit("AAR already contains META-INF/licenses; refusing to overwrite notices")
with zipfile.ZipFile(aar, "a", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
    for path in sorted(destination.rglob("*")):
        if not path.is_file():
            continue
        name = "META-INF/licenses/" + path.relative_to(destination).as_posix()
        info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        package.writestr(info, path.read_bytes())
PY
mkdir -p "$work/out"
for shipped_dir in "$work/aar/jni/"*/; do
	abi="$(basename "$shipped_dir")"
	mkdir -p "$work/debug/$abi"
	pairs=()
	for shipped in "$shipped_dir"*.so; do
		name="$(basename "$shipped")"
		candidates=()
		while IFS= read -r candidate; do
			candidates+=("$candidate")
		done < <(debug_candidates "$abi" "$name")
		unstripped=
		if [ ${#candidates[@]} -eq 0 ]; then
			echo "build-aar.sh: no unstripped $abi/$name under build/mpv, build/intermediates or the NDK" >&2
		else
			unstripped="$(python3 "$symbols" match "$shipped" "${candidates[@]}")" || true
		fi
		if [ -z "$unstripped" ]; then
			if [ "$name" = libc++_shared.so ]; then
				echo "build-aar.sh: $abi/$name is the NDK's and has no unstripped copy here; packing $abi without it"
				continue
			fi
			echo "build-aar.sh: $abi/$name ships without a debug file a crash in it could be matched to" >&2
			exit 1
		fi
		"$objcopy" --only-keep-debug "$unstripped" "$work/debug/$abi/$name"
		pairs+=(--pair "$shipped" "$work/debug/$abi/$name")
	done
	python3 "$symbols" pack "$work/out/mpv-android-$abi-symbols.zip" "${pairs[@]}"
done

mkdir -p "$root/dist/release"
cp "$aar" "$root/dist/release/mpv-android.aar"
python3 "$here/bundle-engine-metadata.py" "$root/dist/release/mpv-android.aar" "$here/build/mpv"
mv "$work/out/"*.zip "$root/dist/release/"
echo "built dist/release/mpv-android.aar and its mpv-android-<abi>-symbols.zip from $tarballs"
