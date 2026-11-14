#!/usr/bin/env python3
"""Keep Linux ARM64 builds native to the public GitHub-hosted runner."""

from pathlib import Path


workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
job_start = workflow.index("  build-linux-arm64:")
job_end = workflow.index("\n  build-windows:", job_start)
job = workflow[job_start:job_end]
job_config = "\n".join(
    line for line in job.splitlines() if not line.lstrip().startswith("#")
)

assert "runs-on: ubuntu-24.04-arm" in job_config
assert "ARCH=aarch64 bash platforms/linux/container-build.sh" in job_config
assert "name: linux-aarch64" in job_config
assert "./dist/release/*.tar.zst" in job_config
assert "libmpv-linux-aarch64-symbols.zip" in job_config
for obsolete in ("self-hosted", "private-apple", "Colima", "colima", "NFS_STORAGE", "kspld0", "/Volumes/"):
    assert obsolete not in job_config, f"Linux ARM64 must not depend on Mac-backed path: {obsolete}"
