#!/usr/bin/env python3
"""Verify SDK integrity and keep proprietary build inputs out of packages."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from prepare_android_qairt import REQUIRED, NOTICES, cache_valid, extract_headers


class QairtHeadersTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / 'sdk.zip'
        self.destination = self.root / 'private-headers'
        self.pin = {'version': 'test', 'sha256': ''}

    def fixture(self, extra=None):
        with zipfile.ZipFile(self.archive, 'w') as output:
            for name in REQUIRED + NOTICES:
                output.writestr('qairt/test/' + name, 'pinned ' + name)
            output.writestr('qairt/test/lib/libQnnHtp.so', 'SDK binary is not staged')
            if extra:
                output.writestr(extra, 'unsafe')
        self.pin['sha256'] = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def test_only_headers_and_original_notices_are_staged(self):
        self.fixture()
        extract_headers(self.archive, self.destination, self.pin)
        self.assertTrue(cache_valid(self.destination, self.pin))
        self.assertFalse((self.destination / 'lib').exists())
        for name in REQUIRED + NOTICES:
            self.assertTrue((self.destination / name).is_file())

    def test_archive_mismatch_writes_nothing(self):
        self.fixture()
        self.pin['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            extract_headers(self.archive, self.destination, self.pin)
        self.assertFalse(self.destination.exists())

    def test_unsafe_archive_path_writes_nothing(self):
        self.fixture('qairt/test/include/QNN/../../outside')
        with self.assertRaisesRegex(ValueError, 'Unsafe path'):
            extract_headers(self.archive, self.destination, self.pin)
        self.assertFalse(self.destination.exists())

    def test_changed_cached_header_requires_restage(self):
        self.fixture()
        extract_headers(self.archive, self.destination, self.pin)
        (self.destination / REQUIRED[0]).write_text('corrupt cached input')
        self.assertFalse(cache_valid(self.destination, self.pin))


if __name__ == '__main__':
    unittest.main()
