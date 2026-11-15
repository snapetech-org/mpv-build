#!/usr/bin/env bash
set -euo pipefail

# Shared by the Windows matrix jobs and the one-time host LLVM producer so
# their compiler/runtime environment cannot drift apart.
sudo rm -f /etc/apt/sources.list.d/google-chrome*.list
export DEBIAN_FRONTEND=noninteractive

# GitHub's Ubuntu image may point the Ubuntu suites at its regional Azure
# mirror. That mirror stalled in the centralus hosted runner while the
# canonical archive.ubuntu.com mirror responded immediately. Rewrite only
# that Ubuntu mirror; leave third-party repositories and signed suites intact.
for source in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
  [[ -f "$source" ]] || continue
  if grep -q 'azure.archive.ubuntu.com' "$source"; then
    sudo sed -i \
      -e 's#http://azure.archive.ubuntu.com/ubuntu#https://archive.ubuntu.com/ubuntu#g' \
      -e 's#https://azure.archive.ubuntu.com/ubuntu#https://archive.ubuntu.com/ubuntu#g' \
      "$source"
    echo "Replaced stalled Azure Ubuntu mirror in $source."
  fi
done

apt_options=(
  -o Acquire::Retries=2
  -o Acquire::http::Timeout=15
  -o Acquire::https::Timeout=15
)
sudo apt-get "${apt_options[@]}" update
sudo apt-get "${apt_options[@]}" install -y \
  git cmake ninja-build build-essential pkg-config curl wget unzip \
  zip patch ca-certificates python3 python3-pip autoconf automake libtool \
  libtool-bin bison flex gettext mercurial subversion gyp yasm nasm \
  gcc-multilib g++-multilib clang lld libc++-dev libc++abi-dev \
  libgmp-dev libmpfr-dev libmpc-dev libgcrypt-dev gperf ragel \
  texinfo autopoint re2c asciidoc rst2pdf python3-docutils \
  python3-mako python3-jsonschema p7zip-full ccache
timeout 180s python3 -m pip install --break-system-packages --user \
  --timeout 15 --retries 1 meson
meson_bin="$(python3 -m site --user-base)/bin"
echo "$meson_bin" >> "$GITHUB_PATH"
export PATH="$meson_bin:$PATH"
meson --version
