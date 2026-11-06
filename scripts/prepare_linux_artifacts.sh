#!/usr/bin/env bash
# Provision packaging/publication tools on a fresh private Linux x64 runner.
set -euo pipefail

public=false
if [[ "${1:-}" == --public ]]; then
  public=true
  shift
fi
if (( $# != 0 )); then
  echo 'Usage: prepare_linux_artifacts.sh [--public]' >&2
  exit 1
fi
if [[ "${GITHUB_ACTIONS:-}" != true || "$(uname -s):$(uname -m)" != Linux:x86_64 ]] || \
   { [[ "$public" == false && "${RUNNER_ENVIRONMENT:-}" != self-hosted ]] || [[ "$public" == true && "${RUNNER_ENVIRONMENT:-}" != github-hosted ]]; }; then
  echo 'Artifact tooling must be installed in the private Linux x64 JIT job.' >&2
  exit 1
fi
: "${RUNNER_TEMP:?The job temporary directory is required}"
: "${GITHUB_PATH:?The Actions path file is required}"

# The private runner bootstrap provisions these tools before accepting a job.
# Plan and publish deliberately have no sudo; never install packages here.
version=2.103.3

if [[ "$public" == true ]]; then
  # Transport/packaging tools do not change the keyed compiler inputs. Keep
  # private images immutable; provision only disposable public guests here.
  missing=()
  for tool in zip unzip zstd xz file readelf gh; do
    command -v "$tool" >/dev/null || missing+=("$tool")
  done
  if (( ${#missing[@]} )); then
    sudo apt-get update -o Acquire::Retries=3
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends zip unzip zstd xz-utils file binutils gh
  fi
fi

for tool in bash curl git python3 zip unzip zstd xz tar file readelf sha256sum gh; do
  command -v "$tool" >/dev/null || { echo "Missing artifact tool: $tool; repair the private runner bootstrap" >&2; exit 1; }
done
actual_version="$(gh --version)"
if [[ "$public" == false && "$actual_version" != "gh version $version "* ]]; then
  echo "The private image must provision GitHub CLI $version before admitting artifact jobs." >&2
  exit 1
fi
printf '%s\n' "$actual_version"
zip -v >/dev/null
unzip -v >/dev/null
zstd --version
