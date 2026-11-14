#!/usr/bin/env bash
# Provision packaging/publication tools on a fresh GitHub-hosted Linux x64 runner.
set -euo pipefail

if [[ "${1:-}" == --public ]]; then
  shift
fi
if (( $# != 0 )); then
  echo 'Usage: prepare_linux_artifacts.sh [--public]' >&2
  exit 1
fi
if [[ "${GITHUB_ACTIONS:-}" != true || "$(uname -s):$(uname -m)" != Linux:x86_64 || "${RUNNER_ENVIRONMENT:-}" != github-hosted ]]; then
  echo 'Artifact tooling must be installed in a GitHub-hosted Linux x64 job.' >&2
  exit 1
fi
: "${RUNNER_TEMP:?The job temporary directory is required}"
: "${GITHUB_PATH:?The Actions path file is required}"

# Pin the runner CLI expectation used by the publishing workflow. Public job
# guests are disposable, so missing transport tools may be installed here.
version=2.103.3

missing=()
for tool in zip unzip zstd xz file readelf gh; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
if (( ${#missing[@]} )); then
  sudo apt-get update -o Acquire::Retries=3
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends zip unzip zstd xz-utils file binutils gh
fi

for tool in bash curl git python3 zip unzip zstd xz tar file readelf sha256sum gh; do
  command -v "$tool" >/dev/null || { echo "Missing artifact tool after hosted provisioning: $tool" >&2; exit 1; }
done
actual_version="$(gh --version)"
printf '%s\n' "$actual_version"
zip -v >/dev/null
unzip -v >/dev/null
zstd --version
