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

    def test_native_execution_check_is_on_the_linux_publish_path(self):
        source = (ROOT / 'platforms/linux/container-build.sh').read_text()
        self.assertIn('check_music_dsp_filters.py', source)
        self.assertLess(source.index('check_music_dsp_filters.py'), source.rindex('platforms/linux/package.sh'))
        import json
        driver = json.loads((ROOT / 'platforms/linux/group.json').read_text())['driver']
        self.assertIn('scripts/check_music_dsp_filters.py', driver)


if __name__ == '__main__':
    unittest.main()
