#!/usr/bin/env python3
"""Reject compiler cache corruption, path escapes and target-runtime imports."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from host_llvm_cache import consume, installed_tool_names, llvm_recipe_sha256, prepare, unpack


class HostCacheTest(unittest.TestCase):
    def test_cache_recipe_preserves_target_runtime_resource_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recipe = root / 'toolchain/llvm/llvm.cmake'
            recipe.parent.mkdir(parents=True)
            recipe.write_text('set(clang_version "22")\nExternalProject_Add(llvm)\n')
            args = SimpleNamespace(build=root/'build', winbuild=root,
                                   archive=root/'cache.tar.gz', source=root/'llvm',
                                   image='pinned-image', sha256='a'*64, prefix=root/'install')
            with patch('host_llvm_cache.consume'):
                prepare(args)
            self.assertIn('set(clang_version "22")\n', recipe.read_text())
            self.assertIn('INSTALL_COMMAND', recipe.read_text())
            self.assertIn('--winbuild', recipe.read_text())

    def bundle(self, root, files, contents, extra=(), receipt_fields=None):
        archive = root / 'cache.tar.gz'
        receipt = {'schema': 2, 'files': files}
        receipt.update(receipt_fields or {})
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

    def test_cache_identity_uses_pristine_pinned_recipe_not_mutable_cmake_stamp(self):
        with tempfile.TemporaryDirectory() as temporary:
            winbuild = Path(temporary) / 'winbuild'
            recipe = winbuild / 'toolchain/llvm/llvm.cmake'
            recipe.parent.mkdir(parents=True)
            recipe.write_text('pinned LLVM configure recipe\n')
            subprocess.run(['git', '-C', str(winbuild), 'init', '-q'], check=True)
            subprocess.run(['git', '-C', str(winbuild), 'config', 'user.name', 'Test'], check=True)
            subprocess.run(['git', '-C', str(winbuild), 'config', 'user.email',
                            'test@example.invalid'], check=True)
            subprocess.run(['git', '-C', str(winbuild), 'add', 'toolchain/llvm/llvm.cmake'],
                           check=True)
            subprocess.run(['git', '-C', str(winbuild), 'commit', '-qm', 'pin recipe'],
                           check=True)
            commit = subprocess.check_output(
                ['git', '-C', str(winbuild), 'rev-parse', 'HEAD'], text=True).strip()
            with patch('host_llvm_cache.winbuild_pin', return_value=commit):
                pinned_sha = llvm_recipe_sha256(winbuild)
                recipe.write_text('generated ExternalProject CONFIGURE_COMMAND ""\n')
                self.assertEqual(llvm_recipe_sha256(winbuild), pinned_sha)
                subprocess.run(['git', '-C', str(winbuild), 'add', 'toolchain/llvm/llvm.cmake'],
                               check=True)
                subprocess.run(['git', '-C', str(winbuild), 'commit', '-qm', 'wrong recipe'],
                               check=True)
                with self.assertRaisesRegex(ValueError, 'checkout differs'):
                    llvm_recipe_sha256(winbuild)

    def test_export_keeps_the_legacy_workspace_path_from_install_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = root / 'runner' / 'workspace'
            legacy = root / 'opt/actions-runner/_work/mpv-build/mpv-build'
            real.mkdir(parents=True)
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(real, target_is_directory=True)
            prefix = legacy / 'build/windows/aarch64/install'
            installed = f'-- Installing: {prefix}/bin/llvm-readobj\n'
            log_prefix = Path(os.path.abspath(prefix))
            self.assertEqual(installed_tool_names(installed, log_prefix), {'bin/llvm-readobj'})
            canonical = real / 'build/windows/aarch64/install'
            canonical_log = f'-- Installing: {canonical}/bin/llvm-ar\n'
            self.assertEqual(installed_tool_names(canonical_log, log_prefix), {'bin/llvm-ar'})

    def test_export_discovers_required_aliases_missing_from_old_install_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / 'install'
            (prefix / 'bin').mkdir(parents=True)
            (prefix / 'bin/llvm').write_bytes(b'host compiler')
            for name in ('clang', 'clang++', 'ld.lld', 'llvm-ar', 'llvm-nm', 'llvm-readobj'):
                (prefix / 'bin' / name).symlink_to('llvm')
            discovered = installed_tool_names('-- Installing: /old/cache/install/bin/llvm\n', prefix)
            self.assertTrue({f'bin/{name}' for name in
                             ('clang', 'clang++', 'ld.lld', 'llvm-ar', 'llvm-nm', 'llvm-readobj')}
                            .issubset(discovered))

    def test_regular_host_files_and_relative_aliases_extract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); out = root / 'out'; out.mkdir()
            binary = b'host compiler'
            files = {'bin/llvm': {'sha256': hashlib.sha256(binary).hexdigest(), 'mode': 0o755},
                     'bin/clang': {'link': 'llvm'}}
            archive, digest = self.bundle(root, files, {'bin/llvm': binary})
            unpack(archive, digest, out)
            self.assertEqual((out / 'bin/clang').read_bytes(), binary)

    def test_import_replaces_an_older_host_compiler_only_inside_its_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = root / 'install'
            (prefix / 'bin').mkdir(parents=True)
            (prefix / 'bin/llvm').write_bytes(b'older host compiler')
            (prefix / 'bin/clang').symlink_to('llvm')
            compiler = b'verified shared compiler'
            files = {
                'bin/llvm': {'sha256': hashlib.sha256(compiler).hexdigest(), 'mode': 0o755},
                'bin/clang': {'link': 'llvm'},
            }
            archive, digest = self.bundle(
                root,
                files,
                {'bin/llvm': compiler},
                receipt_fields={'winbuildCommit': 'test-pin', 'llvmRecipeSha256': 'b' * 64},
            )
            args = SimpleNamespace(
                command='install', archive=archive, sha256=digest, source=root/'llvm',
                winbuild=root/'winbuild',
                image='ubuntu-24.04', prefix=prefix,
            )
            with patch('host_llvm_cache.validate'), patch('host_llvm_cache.llvm_pin', return_value='test-pin'):
                consume(args)
            self.assertEqual((prefix / 'bin/llvm').read_bytes(), compiler)
            self.assertEqual((prefix / 'bin/clang').readlink(), Path('llvm'))
            self.assertTrue((prefix / 'host-llvm-cache-receipt.json').is_file())

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
