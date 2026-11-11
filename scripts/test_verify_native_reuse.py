#!/usr/bin/env python3
import copy
import unittest
from verify_native_reuse import ANDROID_JOBS, validate_run


class NativeReuseTests(unittest.TestCase):
    def setUp(self):
        self.run = dict(
            repository={"full_name": "snapetech-org/mpv-build"},
            head_repository={"full_name": "snapetech-org/mpv-build"},
            head_branch="main", event="workflow_dispatch", path=".github/workflows/ci.yml",
            status="completed", conclusion="success", head_sha="a" * 40)
        self.jobs = [{"name": name, "conclusion": "success"} for name in ANDROID_JOBS]

    def test_success(self):
        self.assertEqual(validate_run(self.run, self.jobs, "snapetech-org/mpv-build"), "a" * 40)

    def test_reject_untrusted_or_unfinished_source(self):
        for key, value in [
            ("head_repository", {"full_name": "fork/mpv-build"}),
            ("repository", {"full_name": "fork/mpv-build"}),
            ("head_branch", "feature"), ("event", "pull_request"),
            ("path", ".github/workflows/other.yml"), ("status", "in_progress"),
            ("conclusion", "failure"), ("head_sha", "../main"),
        ]:
            with self.subTest(key=key):
                run = copy.deepcopy(self.run)
                run[key] = value
                with self.assertRaises(ValueError):
                    validate_run(run, self.jobs, "snapetech-org/mpv-build")

    def test_every_abi_and_aar_must_succeed(self):
        for index in range(len(self.jobs)):
            with self.subTest(index=index):
                for conclusion in ("failure", "cancelled", "skipped", None):
                    jobs = copy.deepcopy(self.jobs)
                    jobs[index]["conclusion"] = conclusion
                    with self.assertRaises(ValueError):
                        validate_run(self.run, jobs, "snapetech-org/mpv-build")
                with self.assertRaises(ValueError):
                    validate_run(self.run, self.jobs[:index] + self.jobs[index + 1:], "snapetech-org/mpv-build")

    def test_ambiguous_duplicate_job_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_run(self.run, self.jobs + [self.jobs[0]], "snapetech-org/mpv-build")


if __name__ == "__main__":
    unittest.main()
