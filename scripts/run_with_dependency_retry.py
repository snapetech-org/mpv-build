#!/usr/bin/env python3
"""Retry a Gradle dependency transport failure, preserving every attempt's log.

Compile, test, checksum, authentication and missing-artifact failures are final.
Only the dependency-resolution error in Gradle's failure summary can authorize
a retry; a timeout mentioned elsewhere in a build log cannot do so.
"""

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


def dependency_transport_failure(output: str) -> bool:
    output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
    summaries = re.findall(
        r"\* What went wrong:\s*(.*?)(?=\n[^\n]*\* (?:Try|Exception is):|\Z)",
        output, re.DOTALL,
    )
    if len(summaries) != 1:
        return False
    failure = summaries[0]
    if re.search(
        r"There were failing tests|Compilation (?:error|failed)|Could not find |"
        r"No matching variant|PKIX|SSLHandshakeException|"
        r"(?:checksum|signature|verification) (?:failed|mismatch)|"
        r"Received status code (?:400|401|403|404|410)\b", failure, re.I,
    ):
        return False
    return bool(
        re.search(r"Could not resolve (?:all files|all artifacts|all dependencies|\S+:\S+:\S+)", failure)
        and re.search(r"Could not (?:GET|HEAD) ['\"]https://", failure)
        and re.search(
            r"(?:Read|Connect(?:ion)?) timed out|Connection reset|"
            r"Connection prematurely closed|Received status code (?:408|429|500|502|503|504)\b",
            failure, re.I,
        )
    )


def run(command, log_dir: Path, *, attempts=3, sleep=time.sleep) -> int:
    if not command or not 1 <= attempts <= 3:
        raise ValueError("Pass a command and between one and three attempts")
    log_dir.mkdir(parents=True, exist_ok=False)
    print(f"Dependency retry logs: {log_dir}", flush=True)
    for attempt in range(1, attempts + 1):
        path = log_dir / f"attempt-{attempt}.log"
        with path.open("w", encoding="utf-8") as log:
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace") as process:
                for line in process.stdout:
                    log.write(line)
                    print(line, end="", flush=True)
                status = process.wait()
        if status == 0:
            return 0
        if attempt == attempts or not dependency_transport_failure(path.read_text()):
            return status if status > 0 else 128 - status
        delay = 15 * attempt
        print(f"Transient dependency download failed; retrying in {delay}s "
              f"({attempt + 1}/{attempts}). Evidence: {path}", flush=True)
        sleep(delay)
    raise AssertionError("unreachable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Pass the build command after --")
    parent = Path(tempfile.mkdtemp(prefix="mpv-dependency-retry-", dir=os.environ.get("RUNNER_TEMP")))
    return run(command, parent / "logs")


if __name__ == "__main__":
    sys.exit(main())
