#!/usr/bin/env bash
# Provision packaging/publication tools on a fresh private Linux x64 runner.
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != true || "${RUNNER_ENVIRONMENT:-}" != self-hosted || "$(uname -s):$(uname -m)" != Linux:x86_64 ]]; then
  echo 'Artifact tooling must be installed in the private Linux x64 JIT job.' >&2
  exit 1
fi
: "${RUNNER_TEMP:?The job temporary directory is required}"
: "${GITHUB_PATH:?The Actions path file is required}"

# The private runner bootstrap provisions these tools before accepting a job.
# Plan and publish deliberately have no sudo; never install packages here.
version=2.103.3

for tool in bash curl git python3 zip unzip zstd xz tar file readelf sha256sum gh; do
  command -v "$tool" >/dev/null || { echo "Missing artifact tool: $tool; repair the private runner bootstrap" >&2; exit 1; }
done
actual_version="$(gh --version)"
if [[ "$actual_version" != "gh version $version "* ]]; then
  echo "The private image must provision GitHub CLI $version before admitting artifact jobs." >&2
  exit 1
fi
printf '%s\n' "$actual_version"
zip -v >/dev/null
unzip -v >/dev/null
zstd --version
