#!/usr/bin/env python3
"""Exercise export-tool discovery for cross-compiled Windows DLLs."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from check_plezy_audio_tap_export import commands, missing_symbols


class WindowsExportToolTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mpv-export-tools-")
        self.addCleanup(self.temporary.cleanup)
        self.bindir = Path(self.temporary.name)
        self.binary = self.bindir / "libmpv.dll"
        self.binary.touch()

    def add_tool(self, name):
        tool = self.bindir / name
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)
        return tool

    def test_versioned_llvm_readobj_precedes_host_objdump(self):
        llvm18 = self.add_tool("llvm-readobj-18")
        llvm19 = self.add_tool("llvm-readobj-19")
        objdump = self.add_tool("objdump")

        with patch.dict(os.environ, {"PATH": str(self.bindir)}):
            selected = commands(self.binary)

        self.assertEqual(
            selected,
            [
                [str(llvm19), "--coff-exports", str(self.binary)],
                [str(llvm18), "--coff-exports", str(self.binary)],
                [str(objdump), "-p", str(self.binary)],
            ],
        )

    def test_llvm_readobj_export_names_satisfy_the_pcm_abi(self):
        output = "\n".join(
            f"  Name: {symbol}"
            for symbol in (
                "mpv_plezy_audio_tap_version",
                "mpv_plezy_audio_tap_enable",
                "mpv_plezy_audio_tap_read",
                "mpv_plezy_audio_tap_read_next",
            )
        )
        self.assertEqual(missing_symbols(output), [])


if __name__ == "__main__":
    unittest.main()
