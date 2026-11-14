# Public hosted build toolchains

GitHub-hosted runners are the default for mpv builds, tests, scans, packaging,
release publication and maintenance workflows. Preserve each job's target OS
and architecture. The MacBook Air is not required for unsigned Apple binaries,
native Linux ARM64, or any other mpv build.

## Platform routes

- **Apple:** Build and test unsigned Apple frameworks on hosted `macos-26`.
  Install required Homebrew tools in the disposable job and verify the pinned
  Xcode SDKs, `glslang` version and Rust targets before building. This
  repository has no Apple signing step.
- **Linux x86_64:** Build in the content-addressed Ubuntu 24.04 container on
  hosted `ubuntu-24.04`. No private JIT route is configured.
- **Linux ARM64:** Build natively in that same pinned container on hosted
  `ubuntu-24.04-arm`. There is no Mac VM, Colima, Tailnet mount or NFS
  dependency.
- **Windows x86_64 and ARM64:** Cross-build both targets from an x64 Linux
  host on hosted `ubuntu-24.04`. No private JIT route is configured.
- **Android:** Build the four native ABI archives and AAR on hosted
  `ubuntu-24.04`. Java, the pinned NDK and SDK components are installed by the
  workflow; no private proxy or preinstalled JIT image is required.
- **Artifact plan and publication:** Use hosted `ubuntu-24.04` for stale-key
  calculation, group publication and manifest updates. The workflow helper
  provisions missing packaging tools on that disposable runner.

The legacy `private` value accepted by `publish.yml` is a compatibility alias
and routes to public hosted runners. New dispatches use `public`. No build,
test, scan, package, release, or maintenance job in this repository uses
private JIT.

## Validation and recovery

The `CI` workflow and the workflow source guards check the hosted selectors,
Android Java/SDK ordering, Windows compiler memory setup, Apple toolchain pins,
and artifact inputs. A successful compiler job is not publication: verify its
expected artifact and content key, then verify the published manifest.

An old run retains its original workflow revision. Do not restart active runs
to pick up a fix. Let active jobs finish; then validate a new revision through
the normal release controller, which reuses verified published groups and
rebuilds only missing content keys.
