#!/usr/bin/env python3
"""Exercise archive fallback, byte identity and unsafe/pre-existing source refusal."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import prepare_android_lua as lua


class LuaDownloadTests(unittest.TestCase):
    def archive(self, name="lua-5.2.4/src/lua.c"):
        result = io.BytesIO()
        with tarfile.open(fileobj=result, mode="w:gz") as archive:
            entry = tarfile.TarInfo(name)
            entry.size = 3
            archive.addfile(entry, io.BytesIO(b"lua"))
        return result.getvalue()

    def prepare(self, root, raw, fetch):
        pin = {"version": "5.2.4", "sha256": hashlib.sha256(raw).hexdigest(), "url": "https://upstream.invalid/lua.tar.gz"}
        with patch.object(lua.keys, "load_versions", return_value={}), patch.object(lua.keys, "resolved_pins", return_value=pin):
            lua.prepare(root, fetch)

    def test_fallback_preserves_pinned_source_and_receipt(self):
        raw = self.archive()
        requested = []
        def fetch(url):
            requested.append(url)
            if len(requested) == 1:
                raise OSError("unavailable")
            return raw
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare(root, raw, fetch)
            self.assertEqual(len(requested), 2)
            target = root / "platforms/android/deps/lua"
            self.assertEqual((target / "src/lua.c").read_bytes(), b"lua")
            self.assertEqual(json.loads((target / ".plezyng-source.json").read_text())["sha256"], hashlib.sha256(raw).hexdigest())
            self.prepare(root, raw, lambda url: self.fail("verified source was downloaded again"))

    def test_bad_checksum_creates_no_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "checksum"):
                self.prepare(root, self.archive(), lambda url: b"changed bytes")
            self.assertFalse((root / "platforms/android/deps/lua").exists())

    def test_unverified_existing_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "platforms/android/deps/lua"
            target.mkdir(parents=True)
            (target / "keep").write_text("existing source")
            with self.assertRaisesRegex(ValueError, "receipt"):
                self.prepare(root, self.archive(), lambda url: b"")
            self.assertEqual((target / "keep").read_text(), "existing source")

    def test_archive_traversal_is_rejected(self):
        raw = self.archive("lua-5.2.4/../../outside")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(tarfile.FilterError):
                self.prepare(root, raw, lambda url: raw)
            self.assertFalse((root / "outside").exists())


if __name__ == "__main__":
    unittest.main()
