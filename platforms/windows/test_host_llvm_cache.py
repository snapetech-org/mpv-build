#!/usr/bin/env python3
"""Reject compiler cache corruption, path escapes and target-runtime imports."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from host_llvm_cache import normalized_config, prepare, unpack


class HostCacheTest(unittest.TestCase):
    def test_cache_recipe_preserves_target_runtime_resource_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recipe = root / 'toolchain/llvm/llvm.cmake'
            recipe.parent.mkdir(parents=True)
            recipe.write_text('set(clang_version "22")\nExternalProject_Add(llvm)\n')
            config = root / 'config.txt'; config.write_text('original configure inputs')
            args = SimpleNamespace(build=root/'build', winbuild=root, config=config,
                                   archive=root/'cache.tar.gz', source=root/'llvm',
                                   image='pinned-image', sha256='a'*64, prefix=root/'install')
            with patch('host_llvm_cache.consume'):
                prepare(args)
            self.assertIn('set(clang_version "22")\n', recipe.read_text())
            self.assertIn('INSTALL_COMMAND', recipe.read_text())
            self.assertEqual((args.build/'host-llvm-cache/expected-config.txt').read_text(), config.read_text())

    def bundle(self, root, files, contents, extra=()):
        archive = root / 'cache.tar.gz'
        receipt = {'schema': 1, 'files': files}
        with tarfile.open(archive, 'w:gz') as tar:
            payload = json.dumps(receipt).encode()
            member = tarfile.TarInfo('receipt.json'); member.size = len(payload)
            tar.addfile(member, io.BytesIO(payload))
            for name, value in files.items():
                member = tarfile.TarInfo(name)
                if 'link' in value:
                    member.type = tarfile.SYMTYPE; member.linkname = value['link']
                    tar.addfile(member)
                else:
                    payload = contents[name]; member.size = len(payload)
                    tar.addfile(member, io.BytesIO(payload))
            for name in extra:
                tar.addfile(tarfile.TarInfo(name))
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_only_architecture_named_paths_are_normalized(self):
        self.assertEqual(normalized_config('/work/build/windows/aarch64/install'),
                         normalized_config('/work/build/windows/x86_64/install'))
        self.assertNotEqual(normalized_config('-march=armv8'), normalized_config('-march=x86-64'))

    def test_regular_host_files_and_relative_aliases_extract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); out = root / 'out'; out.mkdir()
            binary = b'host compiler'
            files = {'bin/llvm': {'sha256': hashlib.sha256(binary).hexdigest(), 'mode': 0o755},
                     'bin/clang': {'link': 'llvm'}}
            archive, digest = self.bundle(root, files, {'bin/llvm': binary})
            unpack(archive, digest, out)
            self.assertEqual((out / 'bin/clang').read_bytes(), binary)

    def test_wrong_archive_checksum_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); out = root / 'out'; out.mkdir()
            archive, _ = self.bundle(root, {}, {})
            with self.assertRaisesRegex(ValueError, 'archive checksum'):
                unpack(archive, '0' * 64, out)
            self.assertEqual(list(out.iterdir()), [])

    def test_wrong_file_checksum_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); out = root / 'out'; out.mkdir()
            archive, digest = self.bundle(root, {'bin/llvm': {'sha256': '0' * 64, 'mode': 0o755}}, {'bin/llvm': b'changed'})
            with self.assertRaisesRegex(ValueError, 'file checksum'):
                unpack(archive, digest, out)

    def test_paths_target_runtimes_and_external_aliases_are_rejected(self):
        for name, value in [('bin/../escaped', {'link': 'llvm'}),
                            ('lib/clang/22/lib/windows/runtime.a', {'link': 'llvm'}),
                            ('bin/clang', {'link': '/tmp/foreign'})]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); out = root / 'out'; out.mkdir()
                archive, digest = self.bundle(root, {name: value}, {})
                with self.assertRaises(ValueError):
                    unpack(archive, digest, out)

    def test_unrecorded_archive_entries_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); out = root / 'out'; out.mkdir()
            archive, digest = self.bundle(root, {}, {}, extra=['bin/unrecorded'])
            with self.assertRaisesRegex(ValueError, 'inventory'):
                unpack(archive, digest, out)


if __name__ == '__main__':
    unittest.main()
