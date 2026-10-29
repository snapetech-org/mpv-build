#!/usr/bin/env python3
"""Require the additive ordered PCM reader in a packaged libmpv binary."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


SYMBOL = "mpv_plezy_audio_tap_read_next"


def commands(path: Path) -> list[list[str]]:
    if sys.platform == "darwin":
        xcrun = shutil.which("xcrun")
        if xcrun:
            return [[xcrun, "nm", "-gUj", str(path)]]

    candidates = [shutil.which("llvm-nm"), shutil.which("nm")]
    if path.suffix.lower() == ".dll":
        inspectors = [shutil.which("llvm-readobj"), shutil.which("llvm-objdump"), shutil.which("objdump")]
        return [[tool, "--coff-exports" if Path(tool).name.startswith("llvm-readobj") else "-p", str(path)]
                for tool in inspectors if tool]
    flags = ["-D", "--defined-only"] if ".so" in path.name or path.suffix.lower() == ".dylib" else ["-g", "--defined-only"]
    return [[tool, *flags, str(path)] for tool in dict.fromkeys(candidates) if tool]


def has_symbol(output: str) -> bool:
    for line in output.splitlines():
        fields = line.replace(":", " ").split()
        if any(field.lstrip("_") == SYMBOL for field in fields):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="built libmpv shared library or static archive")
    args = parser.parse_args()
    binary = args.binary
    if not binary.is_file():
        parser.error(f"libmpv binary does not exist: {binary}")

    # A universal Apple archive needs the symbol in every architecture,
    # not merely once in nm's combined output.
    if sys.platform == "darwin" and shutil.which("xcrun"):
        archs = subprocess.run(["xcrun", "lipo", "-archs", str(binary)],
                               capture_output=True, text=True, timeout=60)
        if archs.returncode == 0:
            for arch in archs.stdout.split():
                result = subprocess.run(["xcrun", "nm", "-arch", arch, "-gUj", str(binary)],
                                        capture_output=True, text=True, timeout=60)
                if result.returncode or not has_symbol(result.stdout):
                    print(f"error: {binary} has no {SYMBOL} for {arch}", file=sys.stderr)
                    return 1
            if archs.stdout.split():
                print(f"verified {SYMBOL} in all Apple slices: {binary}")
                return 0

    failures: list[str] = []
    for command in commands(binary):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as error:
            failures.append(f"{command[0]}: {error}")
            continue
        if result.returncode != 0:
            failures.append(result.stderr.strip() or f"{command[0]} exited {result.returncode}")
            continue
        if has_symbol(result.stdout):
            print(f"verified {SYMBOL}: {binary}")
            return 0
        failures.append(f"{command[0]} found no exported {SYMBOL}")

    details = "; ".join(item for item in failures if item)
    print(
        f"error: {binary} does not export {SYMBOL}; refusing a subtitle-capture artifact"
        + (f" ({details})" if details else ""),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
