#!/usr/bin/env python3
"""Verify trusted successful native outputs before content-addressed publication."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

ANDROID_JOBS = {
    "bundled-android-release / Build android " + abi
    for abi in ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
} | {"bundled-android-release / Build mpv-android AAR"}


APPLE_JOBS = {"Assemble verified Apple libmpv"}
SOURCE_JOBS = {"android": ANDROID_JOBS, "apple": APPLE_JOBS}


def validate_run(run: dict, jobs: list[dict], repository: str,
                 platform_group: str = "android") -> str:
    if platform_group not in SOURCE_JOBS:
        raise ValueError("Unsupported native reuse platform group")
    if (run.get("head_repository", {}).get("full_name") != repository
            or run.get("repository", {}).get("full_name") != repository
            or run.get("head_branch") != "main"
            or run.get("event") != "workflow_dispatch"
            or run.get("path") != ".github/workflows/ci.yml"
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"):
        raise ValueError("Native reuse requires successful trusted main CI")
    sha = run.get("head_sha", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid native source commit")
    for name in SOURCE_JOBS[platform_group]:
        matches = [job for job in jobs if job.get("name") == name]
        if len(matches) != 1 or matches[0].get("conclusion") != "success":
            raise ValueError("Native source job is not successful: " + name)
    return sha


def content_keys(root: Path, platform_group: str = "android") -> dict:
    return json.loads(subprocess.check_output(
        ["python3", "scripts/keys.py", "keys", "--platform-group", platform_group], cwd=root))


def verify(repository: str, run_id: str, root: Path, platform_group: str = "android") -> None:
    if repository != "snapetech-org/mpv-build" or not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise ValueError("Invalid native source repository or run")

    def api(suffix: str):
        return json.loads(subprocess.check_output(
            ["gh", "api", f"repos/{repository}/actions/runs/{run_id}{suffix}"]))

    sha = validate_run(api(""), api("/jobs?per_page=100")["jobs"], repository, platform_group)
    expected = content_keys(root, platform_group)
    subprocess.run(["git", "fetch", "--no-tags", "origin", sha], cwd=root, check=True)
    with tempfile.TemporaryDirectory(prefix="mpv-native-reuse-") as temporary:
        source = Path(temporary) / "source"
        subprocess.run(["git", "worktree", "add", "--detach", str(source), sha], cwd=root, check=True)
        try:
            actual = content_keys(source, platform_group)
        finally:
            subprocess.run(["git", "worktree", "remove", str(source)], cwd=root, check=True)
    if actual != expected:
        raise ValueError("Native source/build content keys differ")
    print(f"Verified trusted {platform_group} source run {run_id} at {sha}; content keys match")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--platform-group", choices=sorted(SOURCE_JOBS), default="android")
    args = parser.parse_args()
    verify(args.repository, args.run, Path(__file__).resolve().parents[1], args.platform_group)
