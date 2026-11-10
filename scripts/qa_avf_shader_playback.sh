#!/usr/bin/env bash
# Headless playback on a real Metal-capable Mac. Retains exact inputs and logs.
set -euo pipefail
if [[ $# != 2 || "$(uname -s)" != Darwin ]]; then
  echo "Usage on macOS: bash $0 <Libmpv.xcframework.zip> <task-output-directory>" >&2
  exit 2
fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
archive="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
mkdir -p "$2"
output="$(cd "$2" && pwd)"
python3 "$root/scripts/verify_avf_shaders.py" "$archive"
work="$(mktemp -d "$output/avf-playback.XXXXXXXX")"
trap 'printf "Retained playback QA outputs: %s\n" "$work"' EXIT
mkdir -p "$work/MPVKit/Frameworks" "$work/Sources"
python3 - "$root" "$work" <<'PY'
from pathlib import Path
import re
import shutil
import sys
root, work = map(Path, sys.argv[1:])
for name in ('_MPVKit', '_FFmpeg'):
    shutil.copytree(root / 'Sources' / name, work / 'MPVKit/Sources' / name)
text = (root / 'Package.swift').read_text()
text, count = re.subn(r'\.binaryTarget\(\s*name: "Libmpv",\s*url: "[^"\n]+",\s*'
                     r'checksum: "[^"\n]+"\s*\)',
                     '.binaryTarget(name: "Libmpv", path: "Frameworks/Libmpv.xcframework")', text)
if count != 1:
    raise SystemExit('Expected exactly one Libmpv package target')
(work / 'MPVKit/Package.swift').write_text(text)
fixture = root / 'scripts/avf_shader_playback'
shutil.copy2(fixture / 'main.swift', work / 'Sources/main.swift')
for name in ('fixture.mp4', 'identity.glsl'):
    shutil.copy2(fixture / name, work / name)
(work / 'Package.swift').write_text('''// swift-tools-version:5.8
import PackageDescription
let package = Package(name: "ShaderQA", platforms: [.macOS(.v12)],
    dependencies: [.package(path: "MPVKit")],
    targets: [.executableTarget(name: "ShaderQA",
        dependencies: [.product(name: "MPVKit", package: "MPVKit")],
        path: "Sources", linkerSettings: [.linkedFramework("AVFoundation")])])
''')
PY
# Python's ZipFile.extractall flattens framework symlinks into text files.
ditto -x -k "$archive" "$work/MPVKit/Frameworks"
build_root="${AVF_QA_BUILD_ROOT:-$work/build}"
cd "$work"
swift run --scratch-path "$build_root" ShaderQA "$work/fixture.mp4" "$work/identity.glsl" \
  2>&1 | tee "$work/playback.log"
