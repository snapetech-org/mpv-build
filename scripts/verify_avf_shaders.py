#!/usr/bin/env python3
"""Verify the real AVFoundation shader stage in every packaged Apple slice."""

from pathlib import Path
import argparse
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile


FUNCTIONS = {"avf_shaders_create", "avf_shaders_load", "avf_shaders_render", "avf_shaders_destroy"}
IMPORTS = {"_pl_render_image", "_pl_vulkan_create", "_CVMetalTextureCacheCreate"}


def inspect(binary: Path) -> None:
    darwin = sys.platform == "darwin"
    lipo = ["xcrun", "lipo"] if darwin else ["llvm-lipo"]
    nm = ["xcrun", "nm"] if darwin else ["llvm-nm"]
    for tool in (lipo[0], nm[0]):
        if not shutil.which(tool):
            raise RuntimeError(f"Missing archive inspection tool: {tool}")
    architectures = subprocess.check_output([*lipo, "-archs", str(binary)], text=True).split()
    if not architectures:
        raise ValueError(f"No Apple architectures found: {binary}")
    for arch in architectures:
        flags = ["-arch", arch] if darwin else [f"--arch={arch}"]
        output = subprocess.check_output([*nm, *flags, "-g", str(binary)], text=True)
        definitions = {
            fields[-1].removeprefix("_")
            for line in output.splitlines()
            if len(fields := line.split()) >= 2 and fields[-2] == "T"
        }
        if missing := FUNCTIONS - definitions:
            raise ValueError(f"{binary} ({arch}): missing shader functions: {sorted(missing)}")
        # The fallback defines these same functions. Require actual GPU imports
        # from the shader object itself, rather than imports from vo_gpu_next.
        blocks = [block for block in output.split("\n\n") if "avf_shaders.m.o):" in block]
        if not any(IMPORTS <= {line.split()[-1] for line in block.splitlines() if line.split()}
                   for block in blocks):
            raise ValueError(f"{binary} ({arch}): real Vulkan/Metal shader implementation absent")
        print(f"verified AVFoundation Vulkan/Metal shaders: {binary.name} ({arch})")


def verify(path: Path) -> None:
    if path.suffix != ".zip":
        inspect(path)
        return
    with zipfile.ZipFile(path) as archive, tempfile.TemporaryDirectory(
        prefix=".avf-verification-", dir=path.parent
    ) as temporary:
        binaries = [item for item in archive.infolist()
                    if item.filename.endswith("/Libmpv") and ".framework/" in item.filename
                    and not stat.S_ISLNK(item.external_attr >> 16)]
        if not binaries:
            raise ValueError(f"No framework binaries found: {path}")
        for index, item in enumerate(binaries):
            binary = Path(temporary) / f"Libmpv-{index}"
            binary.write_bytes(archive.read(item))
            print(item.filename)
            inspect(binary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    verify(args.archive.resolve())
