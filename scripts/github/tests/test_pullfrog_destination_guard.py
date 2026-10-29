import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_destination_guard.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_destination_guard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40


def identity():
    return {
        "slug": "fr-meyer/agent-toolkit",
        "pr_number": 94,
        "base_ref": "dev",
        "base_sha": BASE_SHA,
        "head_ref": "chore/pullfrog-full-automation",
        "head_sha": HEAD_SHA,
        "head_repository_slug": "fr-meyer/agent-toolkit",
        "default_branch": "main",
        "protected_refs": ["dev", "main"],
    }


def base_payload():
    destination = {
        "destination_repository_slug": "fr-meyer/agent-toolkit",
        "destination_ref": "chore/pullfrog-full-automation",
        "destination_sha": HEAD_SHA,
    }
    return {
        "schema": MODULE.INPUT_SCHEMA,
        "expected": identity(),
        "observed": identity(),
        "request": {
            **destination,
            "attempt": 1,
            "changed_paths": ["scripts/example.py", "docs/example.md"],
        },
        "first_attempt": destination,
    }


class PullfrogDestinationGuardTests(unittest.TestCase):
    def test_allowed_feature_branch_is_accepted(self):
        receipt = MODULE.evaluate_guard(base_payload())
        self.assertEqual(receipt["status"], "allowed")
        self.assertEqual(receipt["blockers"], [])
        self.assertFalse(receipt["policy"]["forks_allowed"])

    def test_each_allowed_prefix_is_accepted(self):
        for prefix in MODULE.ALLOWED_HEAD_PREFIXES:
            with self.subTest(prefix=prefix):
                payload = base_payload()
                branch = prefix + "safe-change"
                for section in ("expected", "observed"):
                    payload[section]["head_ref"] = branch
                payload["request"]["destination_ref"] = branch
                payload["first_attempt"]["destination_ref"] = branch
                self.assertEqual(MODULE.evaluate_guard(payload)["status"], "allowed")

    def test_forbidden_first_attempt_is_rejected(self):
        for branch in ["main", "dev", "release", "feature/not-allowed"]:
            with self.subTest(branch=branch):
                payload = base_payload()
                for section in ("expected", "observed"):
                    payload[section]["head_ref"] = branch
                payload["request"]["destination_ref"] = branch
                payload["first_attempt"]["destination_ref"] = branch
                receipt = MODULE.evaluate_guard(payload)
                self.assertEqual(receipt["status"], "blocked")
                self.assertTrue(
                    {"head_prefix_forbidden", "protected_head_forbidden", "base_or_default_head_forbidden"}
                    & set(receipt["blockers"])
                )

    def test_forbidden_retry_is_rejected(self):
        payload = base_payload()
        payload["request"]["attempt"] = 2
        payload["request"]["destination_ref"] = "chore/different-destination"
        receipt = MODULE.evaluate_guard(payload)
        self.assertIn("destination_ref_mismatch", receipt["blockers"])
        self.assertIn("retry_destination_changed", receipt["blockers"])

    def test_retry_cannot_change_repository_or_sha(self):
        payload = base_payload()
        payload["request"]["attempt"] = 2
        payload["request"]["destination_repository_slug"] = "fr-meyer/other"
        payload["request"]["destination_sha"] = "3" * 40
        receipt = MODULE.evaluate_guard(payload)
        self.assertIn("destination_repository_mismatch", receipt["blockers"])
        self.assertIn("destination_sha_mismatch", receipt["blockers"])
        self.assertIn("retry_destination_changed", receipt["blockers"])

    def test_head_and_base_drift_are_rejected(self):
        variants = {
            "base_ref_drift": ("base_ref", "main"),
            "base_sha_drift": ("base_sha", "3" * 40),
            "head_ref_drift": ("head_ref", "fix/other"),
            "head_sha_drift": ("head_sha", "4" * 40),
        }
        for blocker, (field, value) in variants.items():
            with self.subTest(blocker=blocker):
                payload = base_payload()
                payload["observed"][field] = value
                receipt = MODULE.evaluate_guard(payload)
                self.assertIn(blocker, receipt["blockers"])

    def test_fork_head_is_rejected_even_when_expected_matches(self):
        payload = base_payload()
        payload["expected"]["head_repository_slug"] = "another/agent-toolkit"
        payload["observed"]["head_repository_slug"] = "another/agent-toolkit"
        receipt = MODULE.evaluate_guard(payload)
        self.assertIn("fork_head_forbidden", receipt["blockers"])

    def test_detached_or_full_refs_are_rejected(self):
        for branch in ["", "refs/heads/chore/test", "refs/pull/94/merge", "HEAD"]:
            with self.subTest(branch=branch):
                payload = base_payload()
                for section in ("expected", "observed"):
                    payload[section]["head_ref"] = branch
                payload["request"]["destination_ref"] = branch
                payload["first_attempt"]["destination_ref"] = branch
                receipt = MODULE.evaluate_guard(payload)
                self.assertTrue(
                    {"invalid_expected_head_ref", "invalid_observed_head_ref", "invalid_destination_ref", "head_prefix_forbidden"}
                    & set(receipt["blockers"])
                )

    def test_credentials_and_untrusted_event_fields_cannot_override_destination(self):
        payload = base_payload()
        payload["event"] = {
            "destination_ref": "main",
            "destination_sha": "9" * 40,
            "destination_repository_slug": "attacker/repository",
        }
        baseline = MODULE.evaluate_guard(copy.deepcopy(payload))
        with mock.patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "not-a-real-token",
                "ELEVATED_GITHUB_TOKEN": "not-a-real-token",
                "DESTINATION_REF": "main",
                "DESTINATION_SHA": "9" * 40,
            },
            clear=False,
        ):
            observed = MODULE.evaluate_guard(copy.deepcopy(payload))
        self.assertEqual(observed, baseline)
        self.assertEqual(observed["status"], "allowed")
        self.assertEqual(observed["destination"]["ref"], "chore/pullfrog-full-automation")

    def test_untrusted_request_override_is_rejected(self):
        payload = base_payload()
        payload["request"]["destination_ref"] = "main"
        payload["request"]["destination_sha"] = "9" * 40
        payload["request"]["destination_repository_slug"] = "attacker/repository"
        receipt = MODULE.evaluate_guard(payload)
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("destination_repository_mismatch", receipt["blockers"])
        self.assertIn("destination_ref_mismatch", receipt["blockers"])
        self.assertIn("destination_sha_mismatch", receipt["blockers"])

    def test_governance_workflow_and_validation_authority_paths_are_forbidden(self):
        self.assertTrue(
            {
                "scripts/github/pullfrog_review_fallback.py",
                "scripts/github/tests/test_pullfrog_review_fallback.py",
                "scripts/github/tests/test_pullfrog_review_fallback_workflow_policy.py",
            }.issubset(MODULE.PROTECTED_AUTOMATION_AUTHORITY_PATHS)
        )
        self.assertTrue(
            any(
                ".github/workflows/pullfrog-review-fallback.yml".startswith(prefix)
                for prefix in MODULE.FORBIDDEN_PATH_PREFIXES
            )
        )
        for path in [
            ".github/workflows/pullfrog.yml",
            ".github/actions/unsafe/action.yml",
            ".github/CODEOWNERS",
            ".speculoos/manifest.yaml",
            "templates/reusable-workflows/engine.yml",
            "templates/starter-workflows/trigger.yml",
            "templates/repo-workflow-materialization-manifest.json",
            "templates/workflow-ref-sync-manifest.json",
            *sorted(MODULE.PROTECTED_AUTOMATION_AUTHORITY_PATHS),
        ]:
            with self.subTest(path=path):
                payload = base_payload()
                payload["request"]["changed_paths"] = [path]
                receipt = MODULE.evaluate_guard(payload)
                self.assertIn("forbidden_changed_path", receipt["blockers"])
                self.assertEqual(receipt["paths"]["forbidden"], [path])

    def test_invalid_or_duplicate_changed_paths_are_rejected(self):
        for paths in [
            [],
            ["../secret"],
            ["a//b.py"],
            ["a/./b.py"],
            ["./a.py"],
            ["a/"],
            ["a\u0000.py"],
            ["a.py", "a.py"],
            "a.py",
        ]:
            with self.subTest(paths=paths):
                payload = base_payload()
                payload["request"]["changed_paths"] = paths
                receipt = MODULE.evaluate_guard(payload)
                self.assertIn("invalid_changed_paths", receipt["blockers"])

    def test_protected_ref_set_must_include_base_and_default(self):
        payload = base_payload()
        payload["expected"]["protected_refs"] = ["dev"]
        payload["observed"]["protected_refs"] = ["dev"]
        receipt = MODULE.evaluate_guard(payload)
        self.assertIn("incomplete_expected_protected_refs", receipt["blockers"])
        self.assertIn("incomplete_observed_protected_refs", receipt["blockers"])

    def test_base_and_head_sha_cannot_match(self):
        payload = base_payload()
        payload["expected"]["base_sha"] = HEAD_SHA
        payload["observed"]["base_sha"] = HEAD_SHA
        receipt = MODULE.evaluate_guard(payload)
        self.assertIn("base_head_sha_match", receipt["blockers"])

    def test_attempt_is_bounded(self):
        for attempt in [0, 4, True, "2"]:
            with self.subTest(attempt=attempt):
                payload = base_payload()
                payload["request"]["attempt"] = attempt
                receipt = MODULE.evaluate_guard(payload)
                self.assertIn("invalid_attempt", receipt["blockers"])

    def test_receipt_does_not_copy_paths_or_notes(self):
        payload = base_payload()
        payload["notes"] = "private arbitrary note"
        rendered = json.dumps(MODULE.evaluate_guard(payload), sort_keys=True)
        self.assertNotIn("private arbitrary note", rendered)
        self.assertNotIn("scripts/example.py", rendered)
        self.assertEqual(MODULE.evaluate_guard(payload)["paths"]["count"], 2)

    def test_cli_is_deterministic_and_fail_on_blocked_is_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload_path = root / "payload.json"
            first = root / "first.json"
            second = root / "second.json"
            payload_path.write_text(json.dumps(base_payload()), encoding="utf-8")
            for out in (first, second):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--payload", str(payload_path), "--out", str(out)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            blocked = base_payload()
            blocked["request"]["destination_ref"] = "main"
            payload_path.write_text(json.dumps(blocked), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--payload",
                    str(payload_path),
                    "--out",
                    str(first),
                    "--fail-on-blocked",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
