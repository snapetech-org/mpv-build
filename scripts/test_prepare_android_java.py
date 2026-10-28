#!/usr/bin/env python3
"""Regression cases for private Java networking and incomplete fresh SDKs."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import prepare_android_java as toolchain


class AndroidJavaTests(unittest.TestCase):
    def test_proxy_routes_both_protocols_and_keeps_existing_jvm_settings(self):
        options = toolchain.proxy_options({"HTTPS_PROXY": "http://10.0.2.100:3128",
                                            "JAVA_TOOL_OPTIONS": "-Xmx2g"})
        self.assertTrue(options.startswith("-Xmx2g "))
        for protocol in ("http", "https"):
            self.assertIn(f"-D{protocol}.proxyHost=10.0.2.100", options)
            self.assertIn(f"-D{protocol}.proxyPort=3128", options)

    def test_missing_proxy_is_not_an_uncontrolled_direct_download(self):
        with self.assertRaisesRegex(ValueError, "require HTTPS_PROXY"):
            toolchain.proxy_options({})

    def test_credentials_and_environment_injection_are_rejected(self):
        for proxy in ("http://user:secret@proxy:3128", "http://proxy:3128\nINJECT=yes",
                      "http://proxy", "http://proxy:3128/unexpected"):
            with self.subTest(proxy=proxy), self.assertRaises(ValueError):
                toolchain.proxy_options({"HTTPS_PROXY": proxy})
        with self.assertRaises(ValueError):
            toolchain.proxy_options({"HTTPS_PROXY": "http://proxy:3128",
                                      "JAVA_TOOL_OPTIONS": "-Xmx2g\nINJECT=yes"})

    def test_aar_source_drives_sdk_contract(self):
        packages, files = toolchain.sdk_contract(toolchain.ROOT)
        self.assertIn("platforms;android-36", packages)
        self.assertIn("ndk;29.0.14206865", packages)
        self.assertIn("cmake;4.1.2", packages)
        self.assertTrue(any(path.endswith("llvm-objcopy") for path in files))

    def test_missing_sdk_root_fails_before_invoking_sdkmanager(self):
        with patch.object(subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "SDK root"):
                toolchain.install_sdk({"HTTPS_PROXY": "http://proxy:3128"})
            run.assert_not_called()

    def test_successful_sdkmanager_without_tools_is_a_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            sdk = Path(directory)
            manager = sdk / "cmdline-tools/latest/bin/sdkmanager"
            manager.parent.mkdir(parents=True)
            manager.touch()
            env = {"HTTPS_PROXY": "http://proxy:3128", "ANDROID_HOME": str(sdk)}
            with patch.object(subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "toolchain is incomplete"):
                    toolchain.install_sdk(env)
                self.assertIn("-Dhttps.proxyHost=proxy", run.call_args.kwargs["env"]["JAVA_TOOL_OPTIONS"])
                self.assertTrue(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
