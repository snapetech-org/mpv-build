#!/usr/bin/env python3
"""Pre-stage the pinned Lua bytes when the upstream archive host is unavailable."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request

import keys


def prepare(root: Path, fetch=None) -> None:
    pin = keys.resolved_pins(keys.load_versions(root), "lua", "android")
    expected = {field: pin[field] for field in ("version", "sha256")}
    destination = root / "platforms/android/deps/lua"
    receipt = destination / ".plezyng-source.json"
    if destination.exists():
        if not receipt.is_file() or json.loads(receipt.read_text()) != expected:
            raise ValueError("existing Lua source has no matching verified receipt")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fetch is None:
        def fetch(url):
            with urllib.request.urlopen(url, timeout=30) as response:
                return response.read()
    urls = [f"https://sources.buildroot.net/lua/lua-{pin['version']}.tar.gz", pin["url"]]
    errors = []
    with tempfile.TemporaryDirectory(prefix=".lua-", dir=destination.parent) as temporary:
        temporary = Path(temporary)
        archive = temporary / "lua.tar.gz"
        for url in urls:
            try:
                raw = fetch(url)
            except (OSError, urllib.error.URLError) as error:
                errors.append(f"{url}: {error}")
                continue
            if hashlib.sha256(raw).hexdigest() != pin["sha256"]:
                raise ValueError(f"Lua mirror checksum mismatch: {url}")
            archive.write_bytes(raw)
            break
        else:
            raise RuntimeError("pinned Lua download failed: " + "; ".join(errors))
        with tarfile.open(archive, "r:gz") as source:
            top = f"lua-{pin['version']}"
            if any(member.name.split("/", 1)[0] != top for member in source.getmembers()):
                raise ValueError("unexpected Lua archive root")
            source.extractall(temporary, filter="data")
        extracted = temporary / top
        (extracted / receipt.name).write_text(json.dumps(expected, sort_keys=True) + "\n")
        shutil.move(extracted, destination)
    print(f"Lua {pin['version']}: verified pinned archive {pin['sha256']}")


if __name__ == "__main__":
    prepare(keys.repo_root())
