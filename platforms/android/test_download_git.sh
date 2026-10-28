#!/usr/bin/env bash
# Regression test for Android pinned Git source fallback and commit checking.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
. "$root/platforms/android/include/fetch-git.sh"

temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT

source_repo="$temporary/source"
mirror_repo="$temporary/mirror.git"
destination="$temporary/fetched"
git init --quiet "$source_repo"
git -C "$source_repo" config user.name "Android source fetch test"
git -C "$source_repo" config user.email "android-source-fetch-test@example.invalid"
printf 'pinned dav1d fixture\n' > "$source_repo/source.txt"
git -C "$source_repo" add source.txt
git -C "$source_repo" commit --quiet -m fixture
git -C "$source_repo" tag 1.5.4
git clone --quiet --bare "$source_repo" "$mirror_repo"
expected_commit=$(git -C "$source_repo" rev-parse HEAD)

fetch_pinned_git dav1d "$temporary/missing-primary.git" "$mirror_repo" 1.5.4 "$expected_commit" "$destination"
actual_commit=$(git -C "$destination" rev-parse HEAD)
test "$actual_commit" = "$expected_commit"
test -f "$destination/source.txt"

existing="$temporary/existing"
mkdir "$existing"
printf 'preserve existing content\n' > "$existing/marker.txt"
if fetch_pinned_git dav1d "$temporary/missing-primary.git" "$mirror_repo" 1.5.4 "$expected_commit" "$existing" >/dev/null 2>&1; then
	echo >&2 "fetch_pinned_git overwrote an existing destination"
	exit 1
fi
test "$(cat "$existing/marker.txt")" = 'preserve existing content'

if fetch_pinned_git dav1d "$temporary/missing-primary.git" "$mirror_repo" 1.5.4 "$(printf '0%.0s' {1..40})" "$temporary/mismatch" >/dev/null 2>&1; then
	echo >&2 "fetch_pinned_git accepted a commit that did not match the pin"
	exit 1
fi
test ! -e "$temporary/mismatch"
echo "Android Git source fallback uses the mirror and enforces the commit pin"
