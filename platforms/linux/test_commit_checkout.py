#!/usr/bin/env python3
"""Exercise the real source-checkout helper against an offline Git repository."""

from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("build.sh")


class CommitCheckoutTest(unittest.TestCase):
    def test_untagged_commit_branch_and_mismatched_pin(self):
        source = SCRIPT.read_text()
        start = source.index("checkout_verified_ref() {")
        end = source.index("\n}\n", start) + 3
        helper = source[start:end]
        with tempfile.TemporaryDirectory(prefix="mpv-source-checkout-") as temporary:
            root = Path(temporary)
            origin = root / "origin"
            subprocess.run(["git", "init", "-q", "-b", "main", str(origin)], check=True)
            subprocess.run(["git", "-C", str(origin), "config", "user.name", "Checkout test"], check=True)
            subprocess.run(["git", "-C", str(origin), "config", "user.email", "checkout@example.test"], check=True)
            commits = []
            for value in ["first", "second"]:
                (origin / "source.txt").write_text(value)
                subprocess.run(["git", "-C", str(origin), "add", "source.txt"], check=True)
                subprocess.run(["git", "-C", str(origin), "-c", "commit.gpgsign=false", "commit", "-qm", value], check=True)
                commits.append(subprocess.check_output(["git", "-C", str(origin), "rev-parse", "HEAD"], text=True).strip())
            for ref, expected, succeeds in [
                (commits[0], commits[0], True),
                ("main", commits[1], True),
                (commits[0], commits[1], False),
            ]:
                destination = root / "checkout"
                command = helper + '\ncheckout_verified_ref "$1" "$2" "$3" "$4"'
                result = subprocess.run(
                    ["bash", "-eu", "-c", command, "checkout-test", origin.as_uri(), ref, expected, str(destination)],
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode == 0, succeeds, result.stderr)
                if succeeds:
                    actual = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
                    self.assertEqual(actual, expected)
                else:
                    self.assertFalse(destination.exists())
                    self.assertIn("Git ref mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
