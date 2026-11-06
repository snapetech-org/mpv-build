#!/usr/bin/env python3
"""Cached partial clones must still provide complete pristine patch inputs."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from check_patches import clone_cached_source


class CachedSourceTest(unittest.TestCase):
    def test_promisor_cache_can_materialize_excluded_fate_reference(self):
        with tempfile.TemporaryDirectory(prefix='windows-promisor-test-') as temporary:
            root = Path(temporary); origin = root/'origin'; origin.mkdir()
            def git(directory, *args):
                return subprocess.check_output(['git', '-C', str(directory), *args], text=True).strip()
            git(origin, 'init', '-q')
            reference = origin/'tests/ref/fate/fixture'; reference.parent.mkdir(parents=True)
            reference.write_text('expected fate reference\n')
            (origin/'source.c').write_text('int source;\n')
            git(origin, 'add', '.')
            git(origin, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
            commit = git(origin, 'rev-parse', 'HEAD')
            git(origin, 'config', 'uploadpack.allowFilter', 'true')
            cached = root/'cached'
            subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--sparse', '--no-checkout',
                            origin.as_uri(), str(cached)], check=True)
            git(cached, 'checkout', '-q', '--detach', commit)
            self.assertFalse((cached/'tests/ref/fate/fixture').exists())
            checked = root/'checked'
            clone_cached_source(cached, checked, origin.as_uri())
            git(checked, 'checkout', '-q', '--detach', commit)
            self.assertEqual((checked/'tests/ref/fate/fixture').read_text(), 'expected fate reference\n')
            self.assertFalse((cached/'tests/ref/fate/fixture').exists())


if __name__ == '__main__':
    unittest.main()
