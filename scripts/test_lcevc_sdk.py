#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from fix_lcevc_pkgconfig import normalize
from stage_decoder_notices import stage


class StaticSDKTests(unittest.TestCase):
    def test_runtime_follows_all_static_archives_and_is_idempotent(self):
        original = 'Version: 4.3.1\nLibs: -L"${libdir}" -lstdc++ -lm -llcevc_dec_api -llcevc_dec_common\n'
        actual = normalize(original, 'stdc++')
        self.assertIn('-llcevc_dec_api -llcevc_dec_common -lstdc++ -lm', actual)
        self.assertEqual(normalize(actual, 'stdc++'), actual)

    def test_android_uses_the_packaged_shared_stl_and_bionic_pthreads(self):
        actual = normalize('Libs: -L${libdir} -lc++ -llog -lpthread -llcevc_dec_api -lm\n', 'c++_shared')
        self.assertIn('-llcevc_dec_api -lc++_shared -llog -lm', actual)
        self.assertNotIn('-lpthread', actual)
        self.assertIn('-landroid', actual)

    def test_does_not_rewrite_a_shared_or_unrecognized_descriptor(self):
        with self.assertRaises(ValueError):
            normalize('Libs: -lunknown\n', 'stdc++')

    def test_lcevc_notice_requires_both_source_licensing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'
            prefix = Path(directory) / 'prefix'
            source.mkdir()
            (source / 'COPYING').write_text('copyright terms')
            with self.assertRaises(ValueError):
                stage(source, prefix, 'lcevc_dec')
            (source / 'LICENSE.md').write_text('Additional licensing information: no patent license')
            stage(source, prefix, 'lcevc_dec')
            destination = prefix / 'share/licenses/pleazyng-codecs/lcevc_dec'
            self.assertEqual((destination / 'COPYING').read_text(), 'copyright terms')
            self.assertIn('no patent license', (destination / 'LICENSE.md').read_text())


if __name__ == '__main__':
    unittest.main()
