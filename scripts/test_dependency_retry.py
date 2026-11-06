#!/usr/bin/env python3
"""Exercise retry classification and real subprocess exit propagation."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest

from run_with_dependency_retry import dependency_transport_failure, run


TRANSIENT = """FAILURE: Build failed with an exception.
* What went wrong:
Execution failed for task ':generateDebugUnitTestStubRFile'.
> Could not resolve all files for configuration ':debugUnitTestRuntimeClasspath'.
  > Could not GET 'https://repo.maven.apache.org/maven2/example.pom'.
    > Read timed out
* Try:
> Run with --info.
"""


class DependencyRetryTests(unittest.TestCase):
    def test_dependency_read_timeout_is_retryable(self):
        self.assertTrue(dependency_transport_failure(TRANSIENT))

    def test_rate_limit_and_transient_server_errors_are_retryable(self):
        for status in (408, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                self.assertTrue(dependency_transport_failure(
                    TRANSIENT.replace("Read timed out", f"Received status code {status}")))

    def test_auth_and_missing_artifact_errors_are_final(self):
        for status in (400, 401, 403, 404, 410):
            with self.subTest(status=status):
                self.assertFalse(dependency_transport_failure(
                    TRANSIENT.replace("Read timed out", f"Received status code {status}")))

    def test_compile_test_and_verification_failures_are_final(self):
        for message in ("There were failing tests", "Compilation error", "Checksum mismatch",
                        "Signature failed", "Dependency verification failed", "Could not find example:missing:1",
                        "No matching variant", "PKIX path building failed", "SSLHandshakeException"):
            with self.subTest(message=message):
                self.assertFalse(dependency_transport_failure(
                    TRANSIENT.replace("Read timed out", "Read timed out\n" + message)))

    def test_unrelated_timeout_or_non_dependency_failure_is_final(self):
        self.assertFalse(dependency_transport_failure("Read timed out"))
        self.assertFalse(dependency_transport_failure(
            TRANSIENT.replace("Could not resolve all files", "Unable to run test")))
        self.assertFalse(dependency_transport_failure(
            TRANSIENT.replace("Read timed out", "Artifact is invalid") + "Read timed out"))

    def test_multiple_failure_summaries_are_not_ambiguous_retries(self):
        self.assertFalse(dependency_transport_failure(TRANSIENT + TRANSIENT))

    def test_actual_subprocess_retry_preserves_logs_and_success(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            script = root / "command.py"
            script.write_text(
                "from pathlib import Path\nimport sys\n"
                "counter=Path(__file__).with_suffix('.count')\n"
                "n=int(counter.read_text())+1 if counter.exists() else 1\n"
                "counter.write_text(str(n))\n"
                f"print({TRANSIENT!r} if n==1 else 'BUILD SUCCESSFUL')\n"
                "sys.exit(1 if n==1 else 0)\n")
            delays = []
            self.assertEqual(run([sys.executable, str(script)], root / "logs", sleep=delays.append), 0)
            self.assertEqual(delays, [15])
            self.assertEqual((root / "command.count").read_text(), "2")
            self.assertIn("Read timed out", (root / "logs/attempt-1.log").read_text())
            self.assertIn("BUILD SUCCESSFUL", (root / "logs/attempt-2.log").read_text())

    def test_repeated_transport_failure_is_bounded_and_propagated(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            delays = []
            status = run([sys.executable, "-c", f"print({TRANSIENT!r}); raise SystemExit(7)"],
                         root / "logs", sleep=delays.append)
            self.assertEqual(status, 7)
            self.assertEqual(delays, [15, 30])
            self.assertEqual(len(list((root / "logs").glob("*.log"))), 3)

    def test_actual_test_failure_runs_once_and_propagates(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            delays = []
            status = run([sys.executable, "-c", "print('There were failing tests'); raise SystemExit(4)"],
                         root / "logs", sleep=delays.append)
            self.assertEqual(status, 4)
            self.assertEqual(delays, [])
            self.assertEqual(len(list((root / "logs").glob("*.log"))), 1)


if __name__ == "__main__":
    unittest.main()
