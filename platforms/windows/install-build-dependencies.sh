#!/usr/bin/env bash
set -euo pipefail

# Shared by the Windows matrix jobs and the one-time host LLVM producer so
# their compiler/runtime environment cannot drift apart.
sudo rm -f /etc/apt/sources.list.d/google-chrome*.list
sudo apt-get update
sudo apt-get install -y \
  git cmake ninja-build build-essential pkg-config curl wget unzip \
  zip patch ca-certificates python3 python3-pip autoconf automake libtool \
  libtool-bin bison flex gettext mercurial subversion gyp yasm nasm \
  gcc-multilib g++-multilib clang lld libc++-dev libc++abi-dev \
  libgmp-dev libmpfr-dev libmpc-dev libgcrypt-dev gperf ragel \
  texinfo autopoint re2c asciidoc rst2pdf python3-docutils \
  python3-mako python3-jsonschema p7zip-full ccache
python3 -m pip install --break-system-packages --user meson
meson_bin="$(python3 -m site --user-base)/bin"
echo "$meson_bin" >> "$GITHUB_PATH"
export PATH="$meson_bin:$PATH"
meson --version
