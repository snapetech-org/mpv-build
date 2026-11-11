#!/usr/bin/env bash
set -euo pipefail

readonly rustup_bootstrap_version='1.29.2'
[[ "$(uname -s)" == 'Darwin' ]] || { echo 'rustup bootstrap requires macOS' >&2; exit 1; }
case "$(uname -m)" in
  arm64)
    readonly rustup_target='aarch64-apple-darwin'
    readonly rustup_bootstrap_sha256='f7c7e11eb2e07f006e532a8aaac77b32f4527d305ac386c0c633ca6133d35ca9'
    ;;
  x86_64)
    readonly rustup_target='x86_64-apple-darwin'
    # Official archive checksum, independently verified against the Mach-O.
    readonly rustup_bootstrap_sha256='b9610730ddeef52765723847866fd1e3540b2bf7d5ab0c324aa143a5edf25ba0'
    ;;
  *)
    echo 'rustup bootstrap requires supported 64-bit macOS' >&2
    exit 1
    ;;
esac
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${GITHUB_PATH:?GITHUB_PATH is required}"

cargo_home_path="${CARGO_HOME:-${HOME}/.cargo}"
rustup_home_path="${RUSTUP_HOME:-${HOME}/.rustup}"
rustup_installer_dir="$(mktemp -d "${RUNNER_TEMP}/rustup-init.XXXXXX")"
rustup_installer_file="${rustup_installer_dir}/rustup-init"
cleanup_rustup_installer() {
  rm -f "$rustup_installer_file"
  rmdir "$rustup_installer_dir"
}
trap cleanup_rustup_installer EXIT

rustup_installer_url="https://static.rust-lang.org/rustup/archive/${rustup_bootstrap_version}/${rustup_target}/rustup-init"
curl --proto '=https' --tlsv1.2 --fail --silent --show-error --location \
  "$rustup_installer_url" --output "$rustup_installer_file"
printf '%s  %s\n' "$rustup_bootstrap_sha256" "$rustup_installer_file" | shasum -a 256 --check --status
chmod 0755 "$rustup_installer_file"

export CARGO_HOME="$cargo_home_path"
export RUSTUP_HOME="$rustup_home_path"
"$rustup_installer_file" --yes --no-modify-path --default-toolchain none --profile minimal

test -x "$CARGO_HOME/bin/rustup" || { echo 'pinned rustup install did not create CARGO_HOME/bin/rustup' >&2; exit 1; }
export PATH="$CARGO_HOME/bin:$PATH"
echo "CARGO_HOME=$CARGO_HOME" >> "$GITHUB_ENV"
echo "RUSTUP_HOME=$RUSTUP_HOME" >> "$GITHUB_ENV"
echo "$CARGO_HOME/bin" >> "$GITHUB_PATH"
[[ "$(command -v rustup)" == "$CARGO_HOME/bin/rustup" ]] || { echo 'pinned rustup is not first on PATH' >&2; exit 1; }
rustup --version
