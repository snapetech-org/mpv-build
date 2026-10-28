#!/usr/bin/env python3
"""Provision the Android AAR's Java downloads and exact SDK on a fresh JIT."""

import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def proxy_options(environ):
    raw = environ.get("HTTPS_PROXY") or environ.get("https_proxy")
    if not raw:
        raise ValueError("private Android builds require HTTPS_PROXY")
    proxy = urlsplit(raw if "://" in raw else "http://" + raw)
    if (proxy.scheme != "http" or not proxy.hostname or not proxy.port
            or proxy.username or proxy.password or proxy.query or proxy.fragment
            or proxy.path not in ("", "/")
            or any(c.isspace() for c in raw)):
        raise ValueError("Java downloads require an unauthenticated HTTP proxy URL")
    previous = environ.get("JAVA_TOOL_OPTIONS", "")
    if "\n" in previous or "\r" in previous:
        raise ValueError("JAVA_TOOL_OPTIONS must be one line")
    # Put the reviewed route last so pre-existing properties cannot bypass it.
    return " ".join(filter(None, (
        previous,
        f"-Dhttp.proxyHost={proxy.hostname}", f"-Dhttp.proxyPort={proxy.port}",
        f"-Dhttps.proxyHost={proxy.hostname}", f"-Dhttps.proxyPort={proxy.port}",
        "-Dhttp.nonProxyHosts=localhost|127.*|[::1]",
    )))


def sdk_contract(root):
    source = (root / "platforms/android/lib/build.gradle.kts").read_text()
    def single(pattern):
        matches = re.findall(pattern, source)
        if len(matches) != 1:
            raise ValueError(f"expected one AAR SDK pin matching {pattern}")
        return matches[0]
    api = single(r"\bcompileSdk\s*=\s*(\d+)\b")
    cmake = single(r'\bversion\s*=\s*"(\d+\.\d+\.\d+)"')
    ndk_lines = re.findall(r"(?m)^ndk=(\d+\.\d+\.\d+)$",
                           (root / "toolchain/android.txt").read_text())
    if len(ndk_lines) != 1:
        raise ValueError("expected one pinned Android NDK")
    ndk = ndk_lines[0]
    # AGP 9.3's documented minimum and default Build Tools version.
    build_tools = "36.0.0"
    packages = ["platform-tools", f"platforms;android-{api}",
                f"build-tools;{build_tools}", f"ndk;{ndk}", f"cmake;{cmake}"]
    required = [f"platforms/android-{api}/android.jar",
                f"build-tools/{build_tools}/aapt2", f"ndk/{ndk}/source.properties",
                f"cmake/{cmake}/bin/cmake",
                f"ndk/{ndk}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-objcopy"]
    return packages, required


def install_sdk(environ):
    # This process and sdkmanager both retain the JVM proxy configuration.
    environ = dict(environ, JAVA_TOOL_OPTIONS=proxy_options(environ))
    sdk_value = environ.get("ANDROID_HOME") or environ.get("ANDROID_SDK_ROOT")
    if not sdk_value:
        raise ValueError("setup-android did not provide an Android SDK root")
    sdk = Path(sdk_value)
    managers = sorted((sdk / "cmdline-tools").glob("*/bin/sdkmanager"))
    if not managers:
        raise ValueError("setup-android did not install sdkmanager")
    latest = sdk / "cmdline-tools/latest/bin/sdkmanager"
    manager = latest if latest.is_file() else managers[-1]
    packages, required = sdk_contract(ROOT)
    subprocess.run([str(manager), f"--sdk_root={sdk}", "--channel=3", "--install", *packages],
                   check=True, env=environ)
    missing = [str(sdk / path) for path in required if not (sdk / path).is_file()]
    if missing:
        raise ValueError("Android toolchain is incomplete: " + ", ".join(missing))
    print("Verified Android AAR SDK packages: " + ", ".join(packages))


def main():
    if sys.argv[1:] == ["proxy"]:
        options = proxy_options(os.environ)
        with Path(os.environ["GITHUB_ENV"]).open("a") as output:
            output.write(f"JAVA_TOOL_OPTIONS={options}\n")
        print("Configured the private proxy for sdkmanager and Gradle JVMs")
    elif sys.argv[1:] == ["sdk"]:
        install_sdk(os.environ)
    else:
        raise ValueError("usage: prepare_android_java.py proxy|sdk")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Android Java toolchain: {exc}")
