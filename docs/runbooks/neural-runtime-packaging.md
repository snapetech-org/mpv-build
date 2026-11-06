# Neural runtime packaging

Ordinary compatible libmpv builds include the implemented neural filters. Users
opt in with persisted app Settings; device qualification does not control whether
these filters are compiled. Keep `executionQualified` false until actual runtime
evidence establishes the tested device and path.

- Linux and Windows include the desktop `plezy-pme` filter.
- Android ARM64 includes ANVIL/QNN and the LiteRT adapter. Other Android ABIs
  retain ordinary playback and renderer smoothing.
- Every Apple platform/architecture includes the VideoToolbox motion options.

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
