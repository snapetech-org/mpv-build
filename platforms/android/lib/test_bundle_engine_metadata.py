import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SPEC = importlib.util.spec_from_file_location('metadata', Path(__file__).with_name('bundle-engine-metadata.py'))
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


class BundledEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.aar = self.root / 'engine.aar'
        self.natives = self.root / 'natives'
        for abi in metadata.ABIS:
            for name in ('libavcodec/avcodec.h', 'libavcodec/mediacodec.h',
                         'libavutil/avconfig.h', 'libswresample/swresample.h'):
                p = self.natives / abi / 'include' / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'reviewed matching header\n')
        self.write_aar()

    def write_aar(self, missing=None):
        with zipfile.ZipFile(self.aar, 'w') as archive:
            for abi in metadata.ABIS:
                archive.writestr(f'jni/{abi}/libmpv.so',
                                 b'legacy' if abi == missing else metadata.ENGINE.encode())

    def test_normal_aar_contains_all_abis_and_matching_headers(self):
        import json
        metadata.bundle(self.aar, self.natives)
        with zipfile.ZipFile(self.aar) as archive:
            data = json.loads(archive.read('META-INF/plezyng-dv-engine.json'))
            self.assertEqual(data['abis'], list(metadata.ABIS))
            self.assertEqual(data['activation'], 'runtime-settings-default-off')
            self.assertEqual(data['schema_version'], 2)
            for abi in metadata.ABIS:
                self.assertEqual(archive.read(metadata.PREFIX + abi + '/libavcodec/avcodec.h'), b'reviewed matching header\n')

    def test_generated_architecture_headers_are_preserved_per_abi(self):
        (self.natives / 'x86/include/libavutil/avconfig.h').write_bytes(b'AV_HAVE_FAST_UNALIGNED 0')
        metadata.bundle(self.aar, self.natives)
        with zipfile.ZipFile(self.aar) as archive:
            self.assertEqual(archive.read(metadata.PREFIX + 'x86/libavutil/avconfig.h'), b'AV_HAVE_FAST_UNALIGNED 0')
            self.assertEqual(archive.read(metadata.PREFIX + 'arm64-v8a/libavutil/avconfig.h'), b'reviewed matching header\n')

    def test_rejects_mixed_source_headers_without_changing_source(self):
        before = self.aar.read_bytes()
        (self.natives / 'x86/include/libavcodec/avcodec.h').write_bytes(b'different source')
        with self.assertRaisesRegex(ValueError, 'non-generated FFmpeg headers differ'):
            metadata.bundle(self.aar, self.natives)
        self.assertEqual(self.aar.read_bytes(), before)

    def test_rejects_an_abi_without_compiled_engine(self):
        self.write_aar(missing='x86_64')
        before = self.aar.read_bytes()
        with self.assertRaisesRegex(ValueError, 'compiled experimental engine'):
            metadata.bundle(self.aar, self.natives)
        self.assertEqual(self.aar.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
