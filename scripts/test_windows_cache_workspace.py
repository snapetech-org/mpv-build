#!/usr/bin/env python3
"""Exercise real CMake reuse through a moved workspace alias."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('workspace', Path(__file__).with_name('windows_cache_workspace.py'))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CacheWorkspaceTests(unittest.TestCase):
    def test_relocated_graph_runs_without_rebuilding_the_toolchain(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old, new = root / 'private', root / 'hosted'
            source = old / 'build/windows/mpv-winbuild-cmake'
            source.mkdir(parents=True)
            (source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(cache NONE)\nadd_custom_target(check ALL COMMAND "${CMAKE_COMMAND}" -E touch "${CMAKE_BINARY_DIR}/reused")\n')
            build = old / 'build/windows/x86_64'
            subprocess.run(['cmake', '-S', str(source), '-B', str(build)], check=True, stdout=subprocess.DEVNULL)
            self.assertEqual(module.cached_root(build / 'CMakeCache.txt'), old)
            old.rename(new)
            old.symlink_to(new, target_is_directory=True)
            subprocess.run(['cmake', '-S', str(source), '-B', str(build)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(['cmake', '--build', str(build)], check=True, stdout=subprocess.DEVNULL)
            self.assertTrue((new / 'build/windows/x86_64/reused').exists())

    def test_refuses_cache_from_another_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / 'CMakeCache.txt'
            cache.write_text('CMAKE_HOME_DIRECTORY:INTERNAL=/etc\n')
            with self.assertRaises(ValueError):
                module.cached_root(cache)


if __name__ == '__main__':
    unittest.main()
