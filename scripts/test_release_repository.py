#!/usr/bin/env python3
"""Release writes must ignore gh's configured upstream/default repository."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile
import unittest
from unittest.mock import patch

import keys


class ReleaseRepositoryTests(unittest.TestCase):
    def test_views_and_upload_ignore_an_upstream_default(self):
        group = keys.GROUPS["android"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "dist/release"
            release.mkdir(parents=True)
            (release / "probe.aar").write_bytes(b"verified fixture")
            section = {"libraries": {"mpv-android": {"asset": "probe.aar"}}}
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(returncode=0)

            with patch.dict(os.environ, {"GH_REPO": "edde746/mpv-build"}), \
                    patch.object(keys, "load_manifest", return_value={}), \
                    patch.object(keys, "group_section", return_value=section), \
                    patch.object(keys.subprocess, "run", side_effect=run):
                self.assertEqual(keys.cmd_publish_assets(
                    SimpleNamespace(release_dir="dist/release"), root, group), 0)
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[-1][2], "upload")
            for command in calls:
                self.assertEqual(command[command.index("--repo") + 1], "snapetech-org/mpv-build")

    def test_invalid_asset_namespace_stops_before_any_release_operation(self):
        group = replace(keys.GROUPS["android"], asset_base="https://example.org/binaries-android")
        with patch.object(keys.subprocess, "run") as run:
            with self.assertRaises(SystemExit):
                keys.cmd_publish_assets(SimpleNamespace(release_dir="dist/release"), Path("."), group)
            run.assert_not_called()

    def test_fork_namespace_is_explicit_and_not_hardcoded(self):
        group = replace(keys.GROUPS["apple"], asset_base="https://github.com/example/engine/releases/download/binaries-apple")
        self.assertEqual(keys.release_repository(group), "example/engine")


if __name__ == "__main__":
    unittest.main()
