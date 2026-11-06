# Neural runtime packaging

Ordinary compatible libmpv builds include the implemented neural filters. Users
opt in with persisted app Settings; device qualification does not control whether
these filters are compiled. Keep `executionQualified` false until actual runtime
evidence establishes the tested device and path.

- Linux and Windows include the desktop `plezy-pme` filter.
- Android ARM64 includes ANVIL/QNN and the LiteRT adapter. Other Android ABIs
  retain ordinary playback and renderer smoothing.
- Every Apple platform/architecture includes the VideoToolbox motion options.

Desktop PME also includes overlapped scheduling, multiple display phases from
one inference, playback/display timing feedback, adaptive phase budgets,
low-resolution model resampling and source-cadence telemetry. Pool0170–0179
consolidates the previous motion branches while preserving FEL stream pairing.
Its optional compute device remains independent of the renderer: auto selection
prefers an exact RX7900XT when present, and an explicit device-name override
takes precedence. This is a hardware preference, not a qualification result.

Both Linux libplacebo and MPV build with Vulkan enabled. Linux builds the pinned
Khronos 1.4.309 headers and matching loader because Ubuntu 24.04's development
package predates the engine's minimum. The loader is included in the native
archive and final app beside libmpv; hardware ICD drivers stay system supplied.
Never spoof the pkg-config version to accept an older SDK.
Desktop package inspection requires the actual
PME Vulkan implementation marker as well as the filter/runtime markers and
records pmeVulkan:true. A CPU-only PME build cannot satisfy this contract,
even when archive metadata claims GPU support. Provider/device availability
continues to be checked at runtime.

Windows libmpv hard-imports `vulkan-1.dll`. The Pleazyng Windows app separately
verifies and installs the pinned LunarG loader and its license for x64/ARM64;
see its `windows/CMakeLists.txt`. Absence of that loader from the native dev
archive alone does not prove an app dependency gap. Inspect the final app
bundle before adding a second loader or rebuilding an already qualified engine.

Apple pool0169 anchors compressed audio timing to AVPlayer's observed playhead.
The AVFoundation fallback test covers clock updates when no new samples are
read, and verifies that fallback stops further clock changes.

Apply the complete platform patch series, build, and package normally. Packaging
requires all four ordered PCM exports and neural code markers from each actual
binary (each architecture in an Apple universal archive). Receipts use inspection
schema 4 and bind the archive SHA-256, binary SHA-256, architectures, and filters.
`keys.py` hashes the inspection contract, so old engines cannot retain the same
immutable key after that contract changes. Never rename an older engine to the
new key or claim that metadata establishes compiled inclusion.

Run `python3 scripts/test_inspect_pcm_package.py`,
`python3 scripts/test_prepare_android_qairt.py`, and `bash scripts/test_keys.sh`
before publishing. The key test's disposable text fixtures stub native inspection;
the separate inspector test compiles real ELF shared libraries and verifies that
PCM-only binaries and metadata-only neural claims fail.

Android ARM64 automatically stages the pinned QAIRT SDK headers before building
libmpv. The helper verifies the SDK archive and staged header hashes, retains
original notices, and stages no SDK runtime binaries. Keep this proprietary input
in private task/cache storage, outside public build artifacts and Actions caches.
A local archive may be supplied to avoid downloading it again. Do not publish
SDK source, headers, or the downloaded archive.

Provider libraries, model packs, and the app's filter invocation are separate
components. Verify the final app bundle as well as libmpv; a filter receipt alone
does not prove that an inference provider can load or execute on a user's device.

## Consolidated branch fixes (2026-11-06)

The release producer retains the additive changes from the former motion
branches: desktop pool0170–0179, Apple compressed clock pool0169, Android
pause-without-flush pool0180, and the Apple host presentation clock and OSD
lifecycle changes in pool0004. Pool0042 preserves those Apple fields and reset
semantics alongside VideoToolbox interpolation. Do not replace these combined
patches with a whole patch file from an older branch.

`test_audiotrack_timing.sh` compiles the actual patched production functions and
covers retained PCM/raw writes, seek flushes, timestamp qualification and stall
recovery across pause. `test_avf_host_present.sh` checks monotonic post-seek host
stamps and drift detection without accessing a display or GPU. These host tests
do not establish device playback qualification.

The Android device suite includes a pixel comparison for an authored Profile 7
fixture supplied through instrumentation argument `felMediaUrl`. It needs a
stationary center-quarter EL residual during the sampled phase around 1.5 s;
an ordinary arbitrary `mediaUrl` remains suitable for lifecycle tests. Without
`felMediaUrl` the specialized comparison is skipped, not claimed as passing.
Record the fixture hash and device/decoder/render diagnostics when qualifying.
