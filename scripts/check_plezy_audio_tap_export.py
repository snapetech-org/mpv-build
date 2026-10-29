#!/usr/bin/env python3
"""Require the additive ordered PCM reader in a packaged libmpv binary."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


SYMBOL = "mpv_plezy_audio_tap_read_next"
SYMBOLS = ("mpv_plezy_audio_tap_version", "mpv_plezy_audio_tap_enable",
           "mpv_plezy_audio_tap_read", SYMBOL)


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


def has_symbol(output: str, symbol: str = SYMBOL) -> bool:
    for line in output.splitlines():
        fields = line.replace(":", " ").split()
        # Darwin prepends exactly one underscore. ELF may append a default
        # symbol-version name; Windows stdcall decoration is not this C ABI.
        if any(re.fullmatch(r"_?" + re.escape(symbol) + r"(?:@@[A-Za-z0-9_.-]+)?", field) for field in fields):
            return True
    return False


def export_output(output: str, command: list[str], binary: Path) -> str:
    if binary.suffix.lower() != '.dll' or '--coff-exports' in command:
        return output
    # objdump -p prints imports as well. A DLL importing a tap function from
    # another library is not evidence that it exports the ABI itself.
    start = output.find('The Export Tables')
    if start < 0:
        start = output.find('Export Table:')  # LLVM objdump PE format
    if start < 0: return ''
    section = output[start:]
    for marker in ('The Function Table', 'PE File Base Relocations', 'Base Relocation Table', 'Import Table:'):
        end = section.find(marker)
        if end >= 0: section = section[:end]
    return section


def missing_symbols(output: str) -> list[str]:
    return [symbol for symbol in SYMBOLS if not has_symbol(output, symbol)]


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
                missing = missing_symbols(result.stdout)
                if result.returncode or missing:
                    print(f"error: {binary} has an incomplete PCM ABI for {arch}: {missing}", file=sys.stderr)
                    return 1
            if archs.stdout.split():
                print(f"verified all {len(SYMBOLS)} PCM exports in every Apple slice: {binary}")
                return 0

    failures: list[str] = []
    for command in commands(binary):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as error:
            failures.append(f"{command[0]}: {error}")
            continue
        if result.returncode != 0:
            failures.append(result.stderr.strip() or f"{command[0]} exited {result.returncode}")
            continue
        missing = missing_symbols(export_output(result.stdout, command, binary))
        if not missing:
            print(f"verified all {len(SYMBOLS)} PCM exports: {binary}")
            return 0
        failures.append(f"{command[0]} missing exports: {', '.join(missing)}")

    details = "; ".join(item for item in failures if item)
    print(
        f"error: {binary} does not export the complete PCM ABI; refusing a subtitle-capture artifact"
        + (f" ({details})" if details else ""),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
