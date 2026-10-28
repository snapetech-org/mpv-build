#!/usr/bin/env python3
"""Keep the private Linux ARM64 runner's NFS and Colima setup in its workflow."""

from pathlib import Path
import re


workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
job_start = workflow.index("  build-linux-arm64:")
job_end = workflow.index("\n  build-windows:", job_start)
job = workflow[job_start:job_end]

storage_root = "/Volumes/plezyng-native-build-kspld0"
storage_source = "kspld0.local:/mnt/disks/gamespool0/plezyng-native-build-20261027"
assert f"NFS_STORAGE_ROOT: {storage_root}" in job
assert f"NFS_STORAGE_SOURCE: {storage_source}" in job
assert f"RUN_ROOT: {storage_root}/runs/${{{{ github.run_id }}}}-${{{{ github.run_attempt }}}}" in job
assert f"BUILD_ROOT: {storage_root}/runs/${{{{ github.run_id }}}}-${{{{ github.run_attempt }}}}/workspace" in job
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
assert 'runs_root="${storage_root}/runs"' in preflight
assert 'test -d "$runs_root"' in preflight
assert 'test -w "$runs_root"' in preflight
assert 'mktemp -d "${runs_root}/.gha-mount-probe.XXXXXX"' in preflight
assert '/bin/dd if=/dev/urandom of="$probe_dir/probe" bs=1048576 count=1' in preflight
assert 'stat -f %z "$probe_dir/probe"' in preflight
assert 'shasum -a 256 "$probe_dir/probe"' in preflight
assert 'shasum -a 256 | /usr/bin/awk' in preflight

workspace_name = "      - name: Prepare the NFS-backed workspace\n"
workspace_start = job.index(workspace_name)
runtime_end = job.find("\n      - name: ", workspace_start + len(workspace_name))
workspace = job[workspace_start:runtime_end]
assert 'umask 077' in workspace
assert 'case "$RUN_ROOT" in' in workspace
assert 'rm -rf "$RUN_ROOT"' in workspace

runtime_end = job.find("\n      - name: ", runtime_start + len(runtime_name))
if runtime_end == -1:
    runtime_end = len(job)
runtime = job[runtime_start:runtime_end]
assert 'colima start "$COLIMA_PROFILE" --vm-type vz --arch aarch64 --cpus 4 --memory 8 --disk 200' in runtime
assert '--mount "$BUILD_ROOT":w' in runtime
assert '--mount "$NFS_STORAGE_ROOT":w' not in runtime
assert job.count(f"{storage_root}/runs/*") == 2, (
    "workspace creation and cleanup must both be confined to the new NFS root"
)

# Exercise the actual declared paths with today's run identifier and a full
# 64-bit identifier. Lima appends a temporary suffix to its SSH control socket.
def env_value(name: str, run_id: str, attempt: str) -> str:
    match = re.search(rf"^      {name}: (.+)$", job, re.MULTILINE)
    assert match, f"missing {name}"
    return match.group(1).replace("${{ github.run_id }}", run_id).replace(
        "${{ github.run_attempt }}", attempt
    )


for run_id, attempt in (("40644233186", "1"), ("18446744073709551615", "9999")):
    profile = env_value("COLIMA_PROFILE", run_id, attempt)
    lima = env_value("LIMA_HOME", run_id, attempt)
    colima = env_value("COLIMA_HOME", run_id, attempt)
    for socket_path in (
        f"{lima}/colima-{profile}/ssh.sock.1234567890123456",
        f"{colima}/{profile}/docker.sock",
    ):
        assert len(socket_path.encode()) < 104, socket_path
assert '${#socket_path}' in runtime, "runtime must check socket paths before VM startup"
assert 'colima stop "$COLIMA_PROFILE" || true' not in job, (
    "never delete VM storage if stopping its consumer failed"
)
