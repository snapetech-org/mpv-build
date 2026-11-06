#!/usr/bin/env bash
set -euo pipefail

[[ "$(uname -s)/$(uname -m)" == Linux/x86_64 ]] || {
  echo 'Android Rust bootstrap requires the Linux x64 build host' >&2; exit 1;
}
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${GITHUB_PATH:?GITHUB_PATH is required}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rust_version="$(sed -n 's/^rust=//p' "$root/toolchain/android.txt")"
[[ -n "$rust_version" ]] || { echo 'Android Rust version is not pinned' >&2; exit 1; }
readonly rustup_version=1.29.2
readonly rustup_sha256=5be191e8c70a5007074254cb74d78dbfdd25cd5a61c27de7b8e5410122ec24f4
installer_dir="$(mktemp -d "$RUNNER_TEMP/rustup-init.XXXXXX")"
trap 'rm -f "$installer_dir/rustup-init"; rmdir "$installer_dir"' EXIT
curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location --retry 3 \
  "https://static.rust-lang.org/rustup/archive/$rustup_version/x86_64-unknown-linux-gnu/rustup-init" \
  --output "$installer_dir/rustup-init"
printf '%s  %s\n' "$rustup_sha256" "$installer_dir/rustup-init" | sha256sum --check --status
chmod 0755 "$installer_dir/rustup-init"
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
"$installer_dir/rustup-init" --yes --no-modify-path --default-toolchain none --profile minimal
export PATH="$CARGO_HOME/bin:$PATH"
rustup toolchain install "$rust_version" --profile minimal --no-self-update
cargo "+$rust_version" --version
printf 'CARGO_HOME=%s\nRUSTUP_HOME=%s\n' "$CARGO_HOME" "$RUSTUP_HOME" >> "$GITHUB_ENV"
printf '%s\n' "$CARGO_HOME/bin" >> "$GITHUB_PATH"
