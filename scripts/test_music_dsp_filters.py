#!/usr/bin/env python3
"""Music controls must survive the deliberately pruned producer filter lists."""
from pathlib import Path
import re
import unittest

from check_music_dsp_filters import REQUIRED

ROOT = Path(__file__).resolve().parents[1]


class MusicDspBuildTest(unittest.TestCase):
    def test_music_filters_are_enabled_on_each_pruned_platform(self):
        for path in ('platforms/linux/build.sh', 'platforms/android/scripts/ffmpeg.sh',
                     'Sources/BuildScripts/XCFrameworkBuild/main.swift'):
            with self.subTest(platform=path):
                source = (ROOT / path).read_text()
                enabled = set()
                for value in re.findall(r'--enable-filter=([a-z0-9_,*]+)', source):
                    enabled.update(value.split(','))
                self.assertFalse(set(REQUIRED) - enabled, f'{path}: missing {set(REQUIRED) - enabled}')

    def test_public_apple_build_rebuilds_changed_dsp_dependencies(self):
        source = (ROOT / '.github/workflows/ci.yml').read_text()
        apple = source.split('  apple-libmpv:', 1)[1].split('  apple-assemble:', 1)[0]
        self.assertIn('scripts/keys.py stale --platform-group apple', apple)
        self.assertIn('libs="$stale_libraries"', apple)
        self.assertNotIn('make build use-prebuilt libs=libmpv ', apple)

    def test_linux_execution_is_manual_and_architecture_matched(self):
        source = (ROOT / '.github/workflows/ci.yml').read_text().split('  linux-music-dsp:', 1)[1]
        self.assertIn("github.event_name == 'workflow_dispatch'", source)
        self.assertIn("inputs.action_tag == 'ci'", source)
        self.assertIn("inputs.runner_pool_tag == 'public'", source)
        self.assertIn("inputs.target == 'linux'", source)
        self.assertIn('runner: ubuntu-24.04-arm', source)
        self.assertIn('runner: ubuntu-24.04', source)
        self.assertIn('platforms/linux/container-build.sh', source)

    def test_native_execution_check_is_on_the_linux_publish_path(self):
        source = (ROOT / 'platforms/linux/container-build.sh').read_text()
        self.assertIn('check_music_dsp_filters.py', source)
        self.assertLess(source.index('check_music_dsp_filters.py'), source.rindex('platforms/linux/package.sh'))
        import json
        driver = json.loads((ROOT / 'platforms/linux/group.json').read_text())['driver']
        self.assertIn('scripts/check_music_dsp_filters.py', driver)


if __name__ == '__main__':
    unittest.main()
