#!/usr/bin/env python3
"""Check the actual Windows source/patch pairs before the expensive build."""
import argparse
import subprocess
import tempfile
from pathlib import Path
import pin_packages
ROOT = Path(__file__).resolve().parents[2]
def command(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)
def clone_cached_source(cached, source, upstream):
    command('git', 'clone', '--quiet', '--shared', '--no-checkout', str(cached), str(source))
    partial = subprocess.run(['git', '-C', str(cached), 'config', '--get',
                              'remote.origin.promisor'], capture_output=True, text=True)
    if partial.stdout.strip() == 'true':
        # Shared object alternates do not inherit the donor's promisor remote.
        # Fetch missing sparse-checkout blobs from the pinned upstream into
        # this disposable check clone, never by rewriting the active cache.
        command('git', 'remote', 'set-url', 'origin', upstream, cwd=source)
        command('git', 'config', 'core.repositoryformatversion', '1', cwd=source)
        command('git', 'config', 'extensions.partialClone', 'origin', cwd=source)
        command('git', 'config', 'remote.origin.promisor', 'true', cwd=source)
        command('git', 'config', 'remote.origin.partialclonefilter', 'blob:none', cwd=source)
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    versions = pin_packages.load_versions(ROOT)
    with tempfile.TemporaryDirectory(prefix='mpv-windows-patch-check-') as temporary:
        for component in pin_packages.COMPONENTS:
            names = pin_packages.resolve_series(ROOT, component)
            if not names: continue
            pins = pin_packages.resolved_pins(versions, component)
            source = Path(temporary) / component
            cached = args.source_root / component
            if (cached / '.git').exists():
                clone_cached_source(cached, source, pins['url'])
            else:
                source.mkdir()
                command('git', 'init', '--quiet', str(source))
            available = subprocess.run(['git','cat-file','-e',pins['commit']+'^{commit}'],cwd=source,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0
            if not available:
                command('git','fetch','--quiet','--depth','1',pins['url'],pins['commit'],cwd=source)
            command('git','-c','advice.detachedHead=false','checkout','--quiet','--detach',pins['commit'],cwd=source)
            command('python3',str(ROOT/'scripts/patches.py'),'apply',component,'windows',str(source),'--check',cwd=ROOT)
            print(f'Windows {component}: verified {pins["commit"]} with {len(names)} selected patches',flush=True)
if __name__ == '__main__': main()
