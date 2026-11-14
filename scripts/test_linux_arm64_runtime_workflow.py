#!/usr/bin/env python3
"""Keep Linux ARM64 builds native to the public GitHub-hosted runner."""

from pathlib import Path


workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
job_start = workflow.index("  build-linux-arm64:")
job_end = workflow.index("\n  build-windows:", job_start)
job = workflow[job_start:job_end]

assert "runs-on: ubuntu-24.04-arm" in job
assert "ARCH=aarch64 bash platforms/linux/container-build.sh" in job
assert "name: linux-aarch64" in job
assert "./dist/release/*.tar.zst" in job
assert "libmpv-linux-aarch64-symbols.zip" in job
for obsolete in ("self-hosted", "private-apple", "Colima", "colima", "NFS_STORAGE", "kspld0", "/Volumes/"):
    assert obsolete not in job, f"Linux ARM64 must not depend on Mac-backed path: {obsolete}"
