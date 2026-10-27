#!/usr/bin/env python3
"""Keep the private Linux ARM64 job's runtime bootstrap in its checked workflow."""

from pathlib import Path


workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
step_name = "      - name: Start private Linux ARM64 container runtime\n"
assert workflow.count(step_name) == 1, "expected one Linux ARM64 runtime step"
step_start = workflow.index(step_name)
next_step = workflow.find("\n      - name: ", step_start + len(step_name))
if next_step == -1:
    next_step = len(workflow)
step = workflow[step_start:next_step]

install = step.find("brew install colima")
version = step.find("colima --version")
start = step.find("colima start --vm-type vz --arch aarch64")
assert install >= 0 and version >= 0 and start >= 0, (
    "the named runtime step must install and verify Colima before starting "
    "the Linux ARM64 VM"
)
assert install < start and version < start, (
    "Colima must be installed and version-checked before the VM starts"
)
