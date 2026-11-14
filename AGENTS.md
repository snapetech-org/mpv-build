## Runner policy — owner directive, 2026-11-13

Use compatible public GitHub-hosted runners first for every build, test, scan,
package, release, and maintenance job. Preserve the target OS and architecture.
Unsigned Apple builds and tests, including all mpv framework builds, run on
hosted macOS. The MacBook Air is not a build dependency for this repository.

Do not use private ephemeral JIT runners in this repository. Public
GitHub-hosted workflows build Linux x64/ARM64, Windows x64/ARM64, Android, and
unsigned Apple frameworks. The MacBook Air is not a build dependency.

A legacy `private` value in `publish.yml` is hosted-only compatibility for an
already-running release controller. New dispatches use `public`. Remove stale
private-only instructions and selectors when found. Old runs keep the workflow
revision they started with; preserve active jobs. Public pull-request code
receives no secrets and minimal permissions.
