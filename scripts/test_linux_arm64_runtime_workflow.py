#!/usr/bin/env python3
"""Keep the private Linux ARM64 runner's NFS and Colima setup in its workflow."""

from pathlib import Path


workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
job_start = workflow.index("  build-linux-arm64:")
job_end = workflow.index("\n  build-windows:", job_start)
job = workflow[job_start:job_end]

storage_root = "/Volumes/plezyng-native-build-kspld0"
storage_source = "kspld0.local:/mnt/disks/gamespool0/plezyng-native-build-20261027"
assert f"NFS_STORAGE_ROOT: {storage_root}" in job
assert f"NFS_STORAGE_SOURCE: {storage_source}" in job
assert "/Volumes/plezyng-native-build/runs/" not in job, (
    "the Linux ARM64 job must not use the stalled kspls0 workspace"
)
preflight_name = "      - name: Prepare shared temporary directory\n"
runtime_name = "      - name: Start private Linux ARM64 container runtime\n"
assert job.count(preflight_name) == 1
preflight_start = job.index(preflight_name)
runtime_start = job.index(runtime_name)
checkout_start = job.index("      - uses: actions/checkout@v4", preflight_start)
assert preflight_start < checkout_start < runtime_start, (
    "the mount preflight must fail before checkout or Colima startup"
)
preflight_end = job.index("\n      - uses: actions/checkout@v4", preflight_start)
preflight = job[preflight_start:preflight_end]
assert 'expected_mount="${expected_source} on ${storage_root} (nfs,"' in preflight
assert 'mktemp -d "${storage_root}/.gha-mount-probe.XXXXXX"' in preflight
assert 'test "$(/bin/cat "$probe_dir/probe")" = "$probe_content"' in preflight

runtime_end = job.find("\n      - name: ", runtime_start + len(runtime_name))
if runtime_end == -1:
    runtime_end = len(job)
runtime = job[runtime_start:runtime_end]
assert 'colima start "$COLIMA_PROFILE" --vm-type vz --arch aarch64 --cpus 4 --memory 8 --disk 200' in runtime
assert '--mount "$NFS_STORAGE_ROOT":w' in runtime
assert job.count(f"{storage_root}/runs/*") == 2, (
    "workspace creation and cleanup must both be confined to the new NFS root"
)
