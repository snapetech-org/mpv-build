#!/usr/bin/env python3
"""Keep hosted native build workflows aligned with their toolchain contracts."""

import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISH = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
ANDROID = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
WINDOWS_BUILD = (ROOT / "platforms/windows/build.sh").read_text(encoding="utf-8")
RUSTUP_BOOTSTRAP = (ROOT / "scripts/install_pinned_rustup_macos.sh").read_text(
    encoding="utf-8"
)


def job_section(workflow: str, name: str) -> str:
    start_match = re.search(rf"(?m)^  {re.escape(name)}:\s*$", workflow)
    assert start_match, f"workflow has no job named {name}"
    start = start_match.start()
    next_line = workflow.find("\n", start) + 1
    following_job = re.search(r"(?m)^  [A-Za-z0-9_-]+:\s*$", workflow[next_line:])
    end = next_line + following_job.start() if following_job else len(workflow)
    return workflow[start:end]


def named_step(job: str, name: str) -> str:
    marker = f"      - name: {name}\n"
    start = job.index(marker)
    next_step = job.find("\n      - ", start + len(marker))
    return job[start:] if next_step < 0 else job[start:next_step]


def assert_job_timeout(workflow: str, name: str, minutes: int) -> None:
    section = job_section(workflow, name)
    assert re.search(rf"(?m)^    timeout-minutes: {minutes}$", section), (
        f"{name} must have a {minutes}-minute job timeout"
    )


for workflow, name, minutes in (
    (PUBLISH, "tests", 30),
    (PUBLISH, "plan", 15),
    (PUBLISH, "build-apple", 90),
    (PUBLISH, "publish-apple", 30),
    (PUBLISH, "build-linux-x64", 120),
    (PUBLISH, "build-linux-arm64", 120),
    (PUBLISH, "build-windows", 120),
    (PUBLISH, "publish", 30),
    (PUBLISH, "manifest", 15),
    (ANDROID, "natives", 120),
    (ANDROID, "aar", 60),
):
    assert_job_timeout(workflow, name, minutes)


def assert_public_hosted_ubuntu(job: str, label: str) -> None:
    runs_on = re.search(r"(?m)^    runs-on: (.+)$", job)
    assert runs_on, f"{label} has no explicit runner route"
    assert runs_on.group(1) == "ubuntu-24.04", f"{label} must use public hosted Ubuntu"
    assert "self-hosted" not in job, f"{label} must not route to a private runner"
    assert "private-overflow" not in job, f"{label} must not expose private overflow routing"


windows = job_section(PUBLISH, "build-windows")
assert_public_hosted_ubuntu(windows, "Windows cross-build")
assert "arch: [x86_64, aarch64]" in windows, "Windows ARM64 must remain in the build matrix"
windows_cache_restore = named_step(windows, "Restore build state cache")
windows_cache_repair = named_step(windows, "Repair restored Windows workspace path")
assert "python3 scripts/windows_cache_workspace.py" in windows_cache_repair, (
    "the Windows build must restore the original workspace path for cached CMake state"
)
windows_swap = named_step(windows, "Add temporary swap for compiler memory spikes")
for token in (
    "swap_size_gib=8",
    "keep_free_gib=4",
    "sudo fallocate -l",
    "sudo mkswap",
    "sudo swapon",
    "sudo sysctl vm.swappiness=100",
):
    assert token in windows_swap, f"Windows cross-builds must configure safe guest swap: {token}"
assert windows.index(windows_swap) < windows.index(
    named_step(windows, "Build libmpv-windows (${{ matrix.arch }})")
), "compiler swap must be enabled before the Windows build starts"
assert windows.index(windows_cache_restore) < windows.index(windows_cache_repair) < windows.index(
    named_step(windows, "Build libmpv-windows (${{ matrix.arch }})")
), "the cached workspace path must be repaired before CMake reuses the build tree"
for token in (
    'NINJA_WRAPPER_DIR="$WORK/ninja-wrapper"',
    'cat > "$NINJA_WRAPPER_DIR/ninja" <<\'SH\'',
    "--jobs|--load-average|-j|-l)",
    "--jobs=*|--load-average=*|-j*|-l*)",
    'args+=("$arg")',
    'exec /usr/bin/ninja "-j${PLEZY_WINDOWS_NINJA_JOBS}" "${args[@]}"',
    'export PATH="$NINJA_WRAPPER_DIR:$PATH"',
):
    assert token in WINDOWS_BUILD, (
        "the Windows build driver must normalize unsupported job flags, remove load limits, "
        f"and serialize nested Ninja builds: {token}"
    )
assert WINDOWS_BUILD.index('export PATH="$NINJA_WRAPPER_DIR:$PATH"') < WINDOWS_BUILD.index(
    'cmake "${cmake_args[@]}"'
), "the Ninja wrapper must be active before CMake configures nested builds"

wrapper_start = WINDOWS_BUILD.index("<<'SH'\n") + len("<<'SH'\n")
wrapper_end = re.search(r"(?m)^SH\s*$", WINDOWS_BUILD[wrapper_start:])
assert wrapper_end, "the Windows Ninja wrapper heredoc must be terminated"
wrapper_source = textwrap.dedent(
    WINDOWS_BUILD[wrapper_start : wrapper_start + wrapper_end.start()]
).replace("/usr/bin/ninja", '"${NINJA_TEST_BIN}"', 1)
with tempfile.TemporaryDirectory(prefix="mpv-ninja-wrapper-") as temporary:
    temp = Path(temporary)
    wrapper = temp / "ninja-wrapper"
    fake_ninja = temp / "fake-ninja"
    captured_args = temp / "ninja-args"
    fake_ninja.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['NINJA_TEST_ARGS']).write_text('\\0'.join(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    wrapper.write_text(wrapper_source, encoding="utf-8")
    fake_ninja.chmod(0o755)
    wrapper.chmod(0o755)
    env = os.environ.copy()
    env["NINJA_TEST_BIN"] = str(fake_ninja)
    env["NINJA_TEST_ARGS"] = str(captured_args)
    env["PLEZY_WINDOWS_NINJA_JOBS"] = "2"
    subprocess.run(
        [
            str(wrapper),
            "--jobs=1",
            "--jobs",
            "4",
            "-j",
            "5",
            "-j12",
            "-l",
            "0.5",
            "-l5",
            "--load-average=3",
            "--load-average",
            "1",
            "-C",
            "build",
        ],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    assert captured_args.read_text(encoding="utf-8").split("\0") == [
        "-j2",
        "-C",
        "build",
    ], (
        "the wrapper must drop unsupported job/load flags and keep ordinary Ninja arguments"
    )
windows_build_step = named_step(windows, "Build libmpv-windows (${{ matrix.arch }})")
assert "bash platforms/windows/build.sh" in windows_build_step, (
    "the Windows publish job must use the keyed build driver containing the wrapper"
)
assert "Limit Ninja concurrency to the guest memory budget" not in windows, (
    "the serial Ninja wrapper must live in the keyed Windows build driver"
)
windows_install = named_step(windows, "Install dependencies")
windows_meson_tokens = (
    "python3 -m pip install --break-system-packages --user meson",
    'meson_bin="$(python3 -m site --user-base)/bin"',
    'echo "$meson_bin" >> "$GITHUB_PATH"',
    "meson --version",
)
windows_meson_positions = [windows_install.index(token) for token in windows_meson_tokens]
assert windows_meson_positions == sorted(windows_meson_positions), (
    "Windows x64 and ARM64 cross-builds must put the user Meson bin directory on PATH before use"
)

patches = job_section(CI, "patches")
patch_test_tools = named_step(patches, "Install ffmpeg")
assert "--no-install-recommends ffmpeg cmake" in patch_test_tools, (
    "the Android glue regression test uses CMake and the patch-suite job must install it"
)

android_natives = job_section(ANDROID, "natives")
java_setup = android_natives.index("      - name: Set up Java for Android SDK manager")
sdk_install = android_natives.index("bash platforms/android/include/download-sdk.sh")
assert "distribution: temurin" in android_natives[java_setup:sdk_install]
assert "java-version: '17'" in android_natives[java_setup:sdk_install]
assert java_setup < sdk_install, "Java 17 must be installed before sdkmanager runs"
rust_setup = android_natives.index("bash scripts/install_pinned_rustup_linux.sh")
assert sdk_install < rust_setup < android_natives.index("Fetch and patch pinned sources")

android_aar = job_section(ANDROID, "aar")
aar_java = android_aar.index("      - uses: actions/setup-java@v4")
aar_build = android_aar.index("Build the AAR and run its JVM tests")
assert "distribution: temurin" in android_aar[aar_java:aar_build]
assert "java-version: '21'" in android_aar[aar_java:aar_build]
aar_sdk = android_aar.index("uses: android-actions/setup-android@")
aar_verify = android_aar.index("python3 scripts/prepare_android_java.py sdk --public")
assert aar_java < aar_sdk < aar_verify < aar_build, (
    "the hosted runner must install and verify its SDK before Gradle"
)
assert "Configure Java for private runner downloads" not in android_aar

# Packaging/publication happens in fresh guests, not the ABI compiler guest.
artifact_setup = "bash scripts/prepare_linux_artifacts.sh"
assert android_aar.index(artifact_setup) < aar_java
for job_name, operation in (("plan", "Compute stale libraries per group"),
                            ("publish", "Download platform builds")):
    section = job_section(PUBLISH, job_name)
    assert section.index(artifact_setup) < section.index(operation), (
        f"{job_name} must provision artifact tools before consuming binaries"
    )
artifact_tools = (ROOT / "scripts/prepare_linux_artifacts.sh").read_text()
for tool in ("zip", "unzip", "zstd", "gh"):
    assert tool in artifact_tools, f"fresh artifact guests require {tool}"
assert "sudo -n" not in artifact_tools, "metadata jobs must never require elevation"
assert 'version=2.103.3' in artifact_tools, "the verified runner CLI contract must stay explicit"
aar_script = (ROOT / "platforms/android/lib/build-aar.sh").read_text()
assert aar_script.index('command -v "$tool"') < aar_script.index('./gradlew')

apple = job_section(PUBLISH, "build-apple")
assert 'runs-on: macos-26' in apple
assert '"group":"private-apple-builds"' not in apple
assert "Install Apple build tools on the hosted runner" in apple
apple_preflight = named_step(apple, "Verify Apple toolchain and install pinned Meson")
assert "rustup" not in apple_preflight, "Apple preflight must not depend on Homebrew rustup"
for tool in ("wget", "nasm", "sdl2-config", "pkg-config", "glslang", "cmake"):
    assert tool in apple_preflight, f"Apple preflight must check {tool} before building"
assert "glslang --version" in apple_preflight
assert "toolchain/apple.txt" in apple_preflight
swift_base = (ROOT / "Sources/BuildScripts/XCFrameworkBuild/base.swift").read_text()
swift_main = (ROOT / "Sources/BuildScripts/XCFrameworkBuild/main.swift").read_text()
assert 'Utility.shell("brew install' not in swift_base + swift_main, (
    "build jobs must not attempt to mutate the shared Homebrew installation"
)
assert '"PATH": ProcessInfo.processInfo.environment["PATH"] ?? BaseBuild.defaultPath' in swift_base, (
    "compiler subprocesses must retain the pinned Meson venv and Rust toolchain PATH"
)
ffmpeg_dependencies = swift_main.split("let dependencyLibrary = [", 1)[1].split("]", 1)[0]
assert ".libshaderc" not in ffmpeg_dependencies, (
    "FFmpeg 9 removed --enable-libshaderc; its Vulkan shaders use the host glslang compiler"
)
rust_step = named_step(apple, "Bootstrap pinned rustup and install pinned Rust toolchain")
assert "bash scripts/install_pinned_rustup_macos.sh" in rust_step
assert rust_step.index("install_pinned_rustup_macos.sh") < rust_step.index(
    "rustup toolchain install"
)
assert "brew install rustup" not in PUBLISH
assert "RUSTUP_AUTO_INSTALL: '0'" in apple

assert "readonly rustup_bootstrap_version='1.29.2'" in RUSTUP_BOOTSTRAP
assert (
    "readonly rustup_bootstrap_sha256='f7c7e11eb2e07f006e532a8aaac77b32f4527d305ac386c0c633ca6133d35ca9'"
    in RUSTUP_BOOTSTRAP
)
assert "aarch64-apple-darwin" in RUSTUP_BOOTSTRAP
assert "static.rust-lang.org/rustup/archive/" in RUSTUP_BOOTSTRAP
assert "shasum -a 256 --check --status" in RUSTUP_BOOTSTRAP
assert "--no-modify-path --default-toolchain none" in RUSTUP_BOOTSTRAP
assert 'echo "$CARGO_HOME/bin" >> "$GITHUB_PATH"' in RUSTUP_BOOTSTRAP

linux_x64 = job_section(PUBLISH, "build-linux-x64")
assert_public_hosted_ubuntu(linux_x64, "Linux x86_64 build")
for linux_job in ("build-linux-x64", "build-linux-arm64"):
    pcm_contract = named_step(job_section(PUBLISH, linux_job), "Require Plezy ordered PCM ABI")
    assert 'find libmpv-prefix/lib -name libmpv.so -print -quit' in pcm_contract, (
        f"{linux_job} must locate libmpv under its native multiarch library directory"
    )
    assert 'python3 scripts/check_plezy_audio_tap_export.py "$libmpv"' in pcm_contract
build_start = linux_x64.index("Build and package in the pinned container")
date_check = linux_x64.index("Check the tarball and symbols for a build date")
upload = named_step(linux_x64, "Upload platform build")
assert build_start < date_check < linux_x64.index("Upload platform build")
assert "./dist/release/*.tar.zst" in upload
assert "libmpv-linux-x86_64-symbols.zip" in upload
assert "if-no-files-found: error" in upload

assert "python3 scripts/test_ci_toolchain_workflows.py" in CI
assert "python3 scripts/test_linux_arm64_runtime_workflow.py" in CI
assert "python3 scripts/test_ci_toolchain_workflows.py" in PUBLISH

print("Hosted Android, Apple, Linux x64 and Windows toolchain workflow contracts passed.")

# GitHub validates reusable workflow permissions before evaluating job ifs.
# A skipped legacy caller must still allow the callee's artifact read scope.
for workflow, job in ((CI, "android"), (CI, "bundled-android-release"), (PUBLISH, "build-android")):
    assert "      actions: read" in job_section(workflow, job), (
        f"{job} must allow the Android callee to read verified prior-run artifacts"
    )

# Artifact reuse has no installed prefix. Inspect the actual reused archive and
# allow its ARM64 starter to accompany the other three successful native jobs.
natives = job_section(ANDROID, "natives")
assert "if: steps.reuse.outputs.sha == ''" in named_step(natives, "Require Plezy ordered PCM ABI (${{ matrix.abi }})")
reused_pcm = named_step(natives, "Require ordered PCM in reused native package (${{ matrix.abi }})")
assert "if: steps.reuse.outputs.sha != ''" in reused_pcm
assert 'scripts/inspect_pcm_package.py' in reused_pcm and '--expected 1' in reused_pcm
assert "REUSE_ALL: ${{ inputs.reuse-native-run != '' && !(matrix.abi == 'arm64-v8a' && inputs.reuse-arm64-run != '') }}" in natives

# JNI and its packaged development headers must use the engine's exact PCM ABI.
tap_patch = (ROOT / "patches/mpv/pool/0210-plezy-ordered-audio-tap.patch").read_text()
tap_section = tap_patch.split("diff --git a/include/mpv/plezy_audio_tap.h", 1)[1].split("\ndiff --git", 1)[0]
tap_header = "\n".join(line[1:] for line in tap_section.splitlines() if line.startswith("+") and not line.startswith("+++")) + "\n"
assert (ROOT / "platforms/android/lib/src/main/headers/mpv/plezy_audio_tap.h").read_text() == tap_header
assert 'from("src/main/headers") { into("$abi/include") }' in (ROOT / "platforms/android/lib/build.gradle.kts").read_text()

# Exercise host selection without downloading or executing an installer.
host_prefix = RUSTUP_BOOTSTRAP.split('cargo_home_path=', 1)[0]
with tempfile.TemporaryDirectory(prefix='mpv-rustup-host-') as temporary:
    temp = Path(temporary)
    uname = temp / 'uname'
    uname.write_text('#!/bin/sh\nif [ "$1" = "-s" ]; then echo "$TEST_KERNEL"; else echo "$TEST_MACHINE"; fi\n')
    uname.chmod(0o755)
    for kernel, machine, target, digest in (
        ('Darwin', 'arm64', 'aarch64-apple-darwin', 'f7c7e11eb2e07f006e532a8aaac77b32f4527d305ac386c0c633ca6133d35ca9'),
        ('Darwin', 'x86_64', 'x86_64-apple-darwin', 'b9610730ddeef52765723847866fd1e3540b2bf7d5ab0c324aa143a5edf25ba0'),
        ('Darwin', 'i386', None, None),
        ('Linux', 'x86_64', None, None),
    ):
        env = dict(os.environ, PATH=str(temp) + os.pathsep + os.environ['PATH'],
                   TEST_KERNEL=kernel, TEST_MACHINE=machine,
                   RUNNER_TEMP=temporary, GITHUB_ENV=str(temp / 'env'), GITHUB_PATH=str(temp / 'path'))
        result = subprocess.run(['bash', '-c', host_prefix + '\nprintf "%s %s" "$rustup_target" "$rustup_bootstrap_sha256"'],
                                env=env, capture_output=True, text=True)
        if target is None:
            assert result.returncode != 0, (kernel, machine)
        else:
            assert result.returncode == 0 and result.stdout == target + ' ' + digest, result
