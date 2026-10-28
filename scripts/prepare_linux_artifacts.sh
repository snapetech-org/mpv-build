#!/usr/bin/env bash
# Provision packaging/publication tools on a fresh private Linux x64 runner.
set -euo pipefail

if [[ "${GITHUB_ACTIONS:-}" != true || "${RUNNER_ENVIRONMENT:-}" != self-hosted || "$(uname -s):$(uname -m)" != Linux:x86_64 ]]; then
  echo 'Artifact tooling must be installed in the private Linux x64 JIT job.' >&2
  exit 1
fi
: "${RUNNER_TEMP:?The job temporary directory is required}"
: "${GITHUB_PATH:?The Actions path file is required}"

sudo -n apt-get update -o Acquire::Retries=3
sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  -o Acquire::Retries=3 ca-certificates curl git python3 zip unzip zstd xz-utils file binutils

# Ubuntu's older gh can omit release-asset digests from its typed --json output.
# Pin the CLI that publish-assets uses to compare immutable content-addressed bytes.
version=2.103.3
checksum=4c806978ffce1cec70853302a56d70ac6da4f19bae7adca4e1a8ab00633dd91d
archive="$RUNNER_TEMP/gh_${version}_linux_amd64.tar.gz"
curl -fsSL --retry 3 --connect-timeout 30 \
  "https://github.com/cli/cli/releases/download/v${version}/gh_${version}_linux_amd64.tar.gz" \
  -o "$archive"
printf '%s  %s\n' "$checksum" "$archive" | sha256sum -c -
tar -xzf "$archive" -C "$RUNNER_TEMP"
bin="$RUNNER_TEMP/gh_${version}_linux_amd64/bin"
export PATH="$bin:$PATH"
printf '%s\n' "$bin" >> "$GITHUB_PATH"

for tool in bash curl git python3 zip unzip zstd xz tar file readelf sha256sum gh; do
  command -v "$tool" >/dev/null || { echo "Missing artifact tool: $tool" >&2; exit 1; }
done
gh --version
zip -v >/dev/null
unzip -v >/dev/null
zstd --version
