#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
python3 - "$root" "$work/lcevc_probe.h" <<'PY'
from pathlib import Path
import sys
root, output = map(Path, sys.argv[1:])
patch = (root / 'patches/mpv/pool/0904-lcevc-before-hardware-submission.patch').read_text()
section = patch.split('diff --git a/video/decode/lcevc_probe.h b/video/decode/lcevc_probe.h\n', 1)[1]
text = ''.join(line[1:] + '\n' for line in section.splitlines() if line.startswith('+') and not line.startswith('+++'))
assert 'static bool mp_lcevc_probe' in text
output.write_text(text)
PY
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -I"$work" \
    "$root/scripts/test_lcevc_probe.c" -o "$work/probe"
"$work/probe"
