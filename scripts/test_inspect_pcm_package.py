#!/usr/bin/env python3
"""Check neural inclusion against compiled bytes, not archive metadata."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from inspect_pcm_package import inspect, required_motion_features
from keys import pcm_receipt_problems


@unittest.skipUnless(shutil.which('cc') and shutil.which('nm'), 'requires C compiler and nm')
class NativePackageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mpv-inspector-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def package(self, neural=False, metadata=False, complete_pcm=True):
        exports = ['version', 'enable', 'read', 'read_next']
        if not complete_pcm:
            exports.remove('read_next')
        source = '\n'.join(f'int mpv_plezy_audio_tap_{name}(void) {{ return 1; }}' for name in exports)
        if neural:
            source += '\nconst char motion_filter[] = "plezy-pme";'
            source += '\nconst char runtime_entry[] = "pme_runtime_open_from_manifest";'
        (self.root / 'fixture.c').write_text(source)
        binary = self.root / 'libmpv.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-o', str(binary), str(self.root / 'fixture.c')], check=True)
        package = self.root / 'libmpv.zip'
        with zipfile.ZipFile(package, 'w') as archive:
            archive.write(binary, 'lib/libmpv.so')
            if metadata:
                archive.writestr('features.json', '{"pme":true,"neuralFilters":["pme"]}')
                archive.writestr('markers.txt', 'plezy-pme\0pme_runtime_open_from_manifest\0')
        return package

    def test_pcm_only_engine_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'omits.*pme'):
            inspect(self.package(), 1, 'linux')

    def test_metadata_cannot_replace_compiled_filter(self):
        with self.assertRaisesRegex(ValueError, 'omits.*pme'):
            inspect(self.package(metadata=True), 1, 'linux')

    def test_neural_engine_retains_complete_pcm_requirement(self):
        with self.assertRaises(subprocess.CalledProcessError):
            inspect(self.package(neural=True, complete_pcm=False), 1, 'linux')

    def test_receipt_binds_actual_binary_and_neural_coverage(self):
        package = self.package(neural=True)
        receipt = inspect(package, 1, 'linux')
        self.assertEqual(receipt['inspectionSchema'], 4)
        self.assertEqual(receipt['neuralFilters'], {'lib/libmpv.so': {'x86_64': ['pme']}})
        self.assertEqual(receipt['artifactSha256'], hashlib.sha256(package.read_bytes()).hexdigest())
        self.assertFalse(receipt['executionQualified'])
        entry = {'capabilities': receipt, 'checksum': receipt['artifactSha256']}
        self.assertEqual(pcm_receipt_problems(entry, 'x86_64', 1, 'linux'), [])
        receipt['neuralFilters']['lib/libmpv.so']['x86_64'] = []
        self.assertTrue(pcm_receipt_problems(entry, 'x86_64', 1, 'linux'))

    def test_architecture_policy_matches_implemented_filters(self):
        self.assertEqual(required_motion_features('android', 'arm64'), ['anvil', 'litert'])
        self.assertEqual(required_motion_features('android', 'armv7'), [])
        self.assertEqual(required_motion_features('android', 'x86_64'), [])
        self.assertEqual(required_motion_features('apple', 'arm64'), ['videotoolbox'])
        with self.assertRaises(ValueError):
            required_motion_features('unknown', 'arm64')


if __name__ == '__main__':
    unittest.main()
