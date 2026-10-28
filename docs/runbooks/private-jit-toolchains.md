# Private JIT build toolchains

Use the current `main` revision when validating changes. Build jobs are enabled
by explicit `workflow_dispatch` inputs and must use the private runner pool; do
not rerun an old workflow revision to validate newer source fixes.

## Platform routes

- **Windows x86_64 and ARM64:** These are cross-builds on the private Linux x64
  JIT lane in `publish.yml`. They do not start Windows guests and do not run on
  the Mac, so they do not require a Windows guest license. The `aarch64` matrix
  entry produces Windows ARM64 binaries. The workflow installs Meson into the
  runner user's Python site and adds that `bin` directory to `GITHUB_PATH`
  before invoking it.
- **Android:** The native ABI matrix installs Temurin Java 17 before the pinned
  Android SDK manager runs. The AAR job also installs Java 17 before Gradle.
  The NDK version remains pinned in `toolchain/android.txt`.
- **Apple:** Apple binaries run on the private macOS ARM64 JIT lane. The job
  verifies the provisioned Xcode SDKs and native tools, then installs the
  pinned rustup-init 1.29.2 binary from the official Rust distribution. The
  installer is SHA-256 checked before execution; the Rust compiler version and
  Apple targets remain pinned by `toolchain/apple.txt`.
  Provision `wget`, `nasm`, SDL2 (`sdl2-config`), `pkg-config`, CMake, Ninja,
  Autoconf, Automake, GNU Libtool, Python 3.12 and `glslang` before admitting
  jobs. SDL2 may be installed as Homebrew's `sdl2-compat` formula; verify its
  command rather than assuming a Cellar directory name. FFmpeg 9 no longer
  accepts `--enable-libshaderc`: Vulkan shaders are compiled by the host
  `glslang`, whose version is recorded in `toolchain/apple.txt`. The builder
  preserves the job's PATH and never installs Homebrew packages itself.
- **Linux x86_64:** The private Linux x64 JIT builds and packages the archive
  in the pinned container, verifies build-date-free outputs, then uploads both
  the archive and symbol file as a run artifact.
- **Linux ARM64:** The private Apple Silicon JIT starts a Linux ARM64 VM. Its
  workspace is mounted from the `gamespool0` NFS share at
  `/Volumes/plezyng-native-build-kspld0`; the preflight checks the expected
  export and performs a write/read probe before checkout or Colima startup.
  A run-scoped Colima `c` directory, Lima at the run root, and profile `b` keep Docker and Lima's
  control socket paths below Darwin's 104-byte limit. The runtime checks the
  complete socket paths before starting the VM. Cleanup must stop the VM
  successfully before removing its storage.

## Source guards

The manual `CI` workflow runs `scripts/test_ci_toolchain_workflows.py` and
`scripts/test_linux_arm64_runtime_workflow.py`. These checks protect the runner
routes, Android Java ordering, Windows Meson PATH setup, Apple rustup bootstrap
pin, Linux artifact inputs, and Linux ARM64 scratch mount.

Run the same checks locally after changing a platform workflow:

```sh
python3 scripts/test_ci_toolchain_workflows.py
python3 scripts/test_linux_arm64_runtime_workflow.py
```

## Failure evidence and dispatch

Run `40556704841` used stale source revision `376a0b3`. Its Windows lanes
installed Meson but did not expose the user `bin` directory, and its Android
lanes reached `sdkmanager` without Java. The macOS job failed during the
Homebrew rustup installation. Current `main` contains the Meson PATH, Java 17,
and provisioned Apple toolchain changes; the run cannot validate those commits.

In that same stale run, Linux x86_64 compilation, packaging, and build-date
checks passed. The artifact upload step did not complete, the run contains no
artifact, and its GitHub job-log endpoint currently returns 404. Treat this as
an unresolved artifact-upload failure until a current-main run produces and
lists the expected artifact; do not infer a compiler failure from it.

Before dispatch, confirm the intended source SHA and that no current matrix is
already active. Dispatch one current-main run with the explicit action and
private pool inputs. A platform is complete only after its expected artifact
exists; successful compilation alone is not a published build.
