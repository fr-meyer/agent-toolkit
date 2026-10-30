import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_cloud_remediation.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_cloud_remediation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

COORDINATOR = MODULE.coordinator
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
RESULT_SHA = "3" * 40


def pull_request(head_sha=HEAD_SHA, base_ref="dev"):
    return {
        "number": 94,
        "state": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base": {"ref": base_ref, "sha": BASE_SHA},
        "head": {
            "ref": "chore/pullfrog-full-automation",
            "sha": head_sha,
            "repo": {"full_name": "fr-meyer/agent-toolkit"},
        },
    }


def check(
    name,
    conclusion="success",
    app="pullfrog",
    check_id=100,
    suite_id=50,
    head_sha=HEAD_SHA,
):
    return {
        "id": check_id,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": head_sha,
        "app": {"slug": app},
        "check_suite": {"id": suite_id},
    }


def remediation_receipt(head_sha=HEAD_SHA, base_ref="dev"):
    protected_refs = sorted({"dev", "main", base_ref})
    snapshot = {
        "schema": COORDINATOR.SNAPSHOT_SCHEMA,
        "repository_slug": "fr-meyer/agent-toolkit",
        "repository": {"default_branch": "main"},
        "event": {
            "kind": "pullfrog_review_completed",
            "delivery_id": "check-run:100",
            "head_sha": head_sha,
        },
        "expected_pull_request": pull_request(head_sha, base_ref),
        "observed_pull_request": pull_request(head_sha, base_ref),
        "reviews": [
            {
                "id": 601,
                "commit_id": head_sha,
                "submitted_at": "2026-10-27T10:00:00Z",
                "state": "COMMENTED",
                "body": (
                    "PRIVATE REVIEW TEXT\n"
                    "<!-- PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ -->\n"
                    "<sup>Using `gpt-6.1-sol`</sup>"
                ),
                "user": {"login": "pullfrog[bot]"},
            }
        ],
        "review_comments": [
            {
                "id": 701,
                "pull_request_review_id": 601,
                "commit_id": head_sha,
                "path": "scripts/example.py",
                "line": 12,
                "body": "PRIVATE COMMENT TEXT",
                "user": {"login": "pullfrog[bot]"},
            }
        ],
        "files": [{"filename": "scripts/example.py"}],
        "check_runs": [
            check("pullfrog", check_id=100, head_sha=head_sha),
            check("pullfrog-approval", "failure", check_id=101, head_sha=head_sha),
            check(
                "ci-required",
                app="github-actions",
                check_id=102,
                suite_id=60,
                head_sha=head_sha,
            ),
            check(
                "speculoos",
                app="github-actions",
                check_id=103,
                suite_id=61,
                head_sha=head_sha,
            ),
        ],
        "history": COORDINATOR._empty_history(),
        "policy": {
            "max_cycles": 3,
            "protected_refs": protected_refs,
            "ci_checks": [{"name": "ci-required", "app_slug": "github-actions"}],
            "speculoos_checks": [
                {"name": "speculoos", "app_slug": "github-actions"}
            ],
        },
    }
    return COORDINATOR.evaluate_snapshot(snapshot)


def empty_ledger():
    return MODULE.build_ledger("fr-meyer/agent-toolkit", 94, [], [], [])


def make_claim(source_head=HEAD_SHA, cycle=0, attempt=1, run_id="123"):
    claim_key = f"fr-meyer/agent-toolkit:94:{source_head}:{cycle}"
    value = {
        "schema": MODULE.CLAIM_SCHEMA,
        "run_id": run_id,
        "run_attempt": 1,
        "workflow_path": MODULE.WORKFLOW_PATH,
        "claim_key": claim_key,
        "cycle_number": cycle,
        "attempt_number": attempt,
        "identity": {
            "repository_slug": "fr-meyer/agent-toolkit",
            "pr_number": 94,
            "base_ref": "dev",
            "base_sha": BASE_SHA,
            "head_ref": "chore/pullfrog-full-automation",
            "head_sha": source_head,
            "head_repository_slug": "fr-meyer/agent-toolkit",
        },
        "destination_policy": {
            "default_branch": "main",
            "protected_refs": ["dev", "main"],
        },
        "review_id": 601 + cycle,
        "finding_count": 1,
        "finding_set_digest": "4" * 64,
        "output_digest": "5" * 64,
        "delivery_id_digest": "6" * 64,
        "coordinator_receipt_digest": "7" * 64,
        "mutation": {
            "provider_allowed": True,
            "provider_push_allowed": False,
            "workflow_publish_allowed_after_validation": True,
            "approval_allowed": False,
            "merge_allowed": False,
            "branch_deletion_allowed": False,
        },
    }
    value["attempt_id"] = MODULE._digest(
        {
            "claim_key": claim_key,
            "run_id": run_id,
            "run_attempt": 1,
            "attempt_number": attempt,
        }
    )
    return value


def action_result(claim):
    return json.dumps(
        {
            "schema": MODULE.ACTION_RESULT_SCHEMA,
            "status": "local_changes_ready",
            "source_head_sha": claim["identity"]["head_sha"],
            "review_id": claim["review_id"],
            "tests_passed": True,
        }
    )


def make_candidate(claim):
    changed_paths = ["scripts/example.py"]
    return {
        "schema": MODULE.CANDIDATE_SCHEMA,
        "run_id": claim["run_id"],
        "attempt_id": claim["attempt_id"],
        "claim_key": claim["claim_key"],
        "cycle_number": claim["cycle_number"],
        "attempt_number": claim["attempt_number"],
        "source_head_sha": claim["identity"]["head_sha"],
        "patch_digest": "8" * 64,
        "patch_bytes": 10,
        "changed_paths": changed_paths,
        "changed_paths_digest": MODULE._digest(changed_paths),
        "action_result_digest": "a" * 64,
        "destination_guard": {"status": "allowed"},
    }


def make_publish_plan(claim, candidate, result_head=RESULT_SHA):
    return {
        "schema": MODULE.PUBLISH_PLAN_SCHEMA,
        "attempt_id": claim["attempt_id"],
        "claim_key": claim["claim_key"],
        "head_ref": claim["identity"]["head_ref"],
        "source_head_sha": claim["identity"]["head_sha"],
        "result_head_sha": result_head,
        "candidate_digest": MODULE._digest(candidate),
        "patch_digest": candidate["patch_digest"],
        "changed_paths_digest": candidate["changed_paths_digest"],
        "destination_guard": {"status": "allowed"},
    }


def artifact_zip(filename, value):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, json.dumps(value))
    return payload.getvalue()


class PullfrogCloudRemediationTests(unittest.TestCase):
    def test_artifact_redirects_are_allowlisted_and_drop_authorization(self):
        handler = MODULE._SafeRedirectHandler()
        request = urllib.request.Request(
            "https://api.github.com/repos/fr-meyer/agent-toolkit/actions/artifacts/1/zip",
            headers={"Authorization": "Bearer secret"},
        )
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://productionresults.example.blob.core.windows.net/artifact.zip?sig=x",
        )
        self.assertIsNotNone(redirected)
        assert redirected is not None
        self.assertFalse(redirected.has_header("Authorization"))
        with self.assertRaisesRegex(MODULE.RemediationError, "unsafe_artifact_redirect"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://example.com/artifact.zip",
            )

    def test_prepare_claim_is_sanitized_and_provider_cannot_push(self):
        receipt = remediation_receipt()
        decision, claim = MODULE.prepare_claim(
            receipt, empty_ledger(), run_id="123", run_attempt=1
        )
        self.assertEqual(decision["status"], "ready")
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertFalse(claim["mutation"]["provider_push_allowed"])
        self.assertFalse(claim["mutation"]["approval_allowed"])
        rendered = json.dumps(claim) + MODULE.build_prompt(claim)
        self.assertNotIn("PRIVATE REVIEW TEXT", rendered)
        self.assertNotIn("PRIVATE COMMENT TEXT", rendered)
        self.assertIn("Do not call `push_branch`", rendered)
        self.assertIn(HEAD_SHA, rendered)

        payload = MODULE.build_pullfrog_payload(claim)
        self.assertTrue(payload["~pullfrog"])
        self.assertEqual(payload["version"], "0.1.102")
        self.assertEqual(payload["type"], "fix_review")
        self.assertEqual(
            payload["event"],
            {
                "trigger": "fix_review",
                "issue_number": 94,
                "is_pr": True,
                "review_id": 601,
                "approved_only": False,
                "branch": "chore/pullfrog-full-automation",
                "authorPermission": "none",
                "silent": True,
            },
        )
        self.assertIn("call `set_output` exactly once", payload["prompt"])
        self.assertNotIn("PRIVATE REVIEW TEXT", json.dumps(payload))

    def test_prepare_claim_cli_emits_identity_for_clean_no_action(self):
        receipt = remediation_receipt()
        receipt["status"] = "clean"
        receipt["would_action"] = "complete"
        receipt["coordinator_blockers"] = []
        receipt["cycle_decision"]["status"] = "clean"
        receipt["cycle_decision"]["action"] = "complete"
        receipt["cycle_decision"]["blockers"] = []
        receipt["cycle_decision"]["review"]["finding_count"] = 0
        receipt["cycle_decision"]["review"]["finding_fingerprints"] = []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_path = root / "receipt.json"
            ledger_path = root / "ledger.json"
            decision_path = root / "decision.json"
            claim_path = root / "claim.json"
            output_path = root / "github-output.txt"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            ledger_path.write_text(json.dumps(empty_ledger()), encoding="utf-8")
            argv = [
                str(SCRIPT),
                "prepare-claim",
                "--receipt",
                str(receipt_path),
                "--ledger",
                str(ledger_path),
                "--run-id",
                "123",
                "--run-attempt",
                "1",
                "--decision-out",
                str(decision_path),
                "--claim-out",
                str(claim_path),
                "--github-output",
                str(output_path),
            ]
            with mock.patch.object(sys, "argv", argv):
                self.assertEqual(MODULE.main(), 0)

            outputs = dict(
                line.split("=", 1)
                for line in output_path.read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(outputs["ready"], "false")
            self.assertEqual(outputs["status"], "no_action")
            self.assertEqual(outputs["reason"], "clean")
            self.assertEqual(outputs["pr_number"], "94")
            self.assertEqual(outputs["base_sha"], BASE_SHA)
            self.assertEqual(outputs["source_head_sha"], HEAD_SHA)
            self.assertFalse(claim_path.exists())

    def test_duplicate_delivery_is_an_idempotent_noop(self):
        receipt = remediation_receipt()
        _, claim = MODULE.prepare_claim(
            receipt, empty_ledger(), run_id="123", run_attempt=1
        )
        assert claim is not None
        terminal = MODULE.terminal_receipt(
            claim,
            "provider_failed",
            "provider_failed",
        )
        ledger = MODULE.build_ledger(
            "fr-meyer/agent-toolkit", 94, [claim], [], [terminal]
        )
        decision, retry = MODULE.prepare_claim(
            receipt, ledger, run_id="124", run_attempt=1
        )
        self.assertEqual(decision["status"], "duplicate_event")
        self.assertIsNone(retry)

    def test_distinct_event_can_retry_failed_attempt_but_not_orphaned_claim(self):
        receipt = remediation_receipt()
        _, claim = MODULE.prepare_claim(
            receipt, empty_ledger(), run_id="123", run_attempt=1
        )
        assert claim is not None
        orphaned = MODULE.build_ledger(
            "fr-meyer/agent-toolkit", 94, [claim], [], []
        )
        receipt["event"]["delivery_id_digest"] = "8" * 64
        decision, retry = MODULE.prepare_claim(
            receipt, orphaned, run_id="124", run_attempt=1
        )
        self.assertEqual(decision["reason"], "orphaned_claim")
        self.assertIsNone(retry)

        failed = MODULE.terminal_receipt(
            claim, "provider_failed", "provider_failed"
        )
        ledger = MODULE.build_ledger(
            "fr-meyer/agent-toolkit", 94, [claim], [], [failed]
        )
        receipt["event"]["delivery_id_digest"] = "9" * 64
        decision, retry = MODULE.prepare_claim(
            receipt, ledger, run_id="124", run_attempt=1
        )
        self.assertEqual(decision["status"], "ready")
        assert retry is not None
        self.assertEqual(retry["attempt_number"], 2)

    def test_successful_terminal_reconstructs_contiguous_history(self):
        claim = make_claim()
        candidate = make_candidate(claim)
        plan = make_publish_plan(claim, candidate)
        terminal = MODULE.terminal_receipt(
            claim,
            "pushed",
            "exact_head_publish_verified",
            result_head_sha=RESULT_SHA,
            publish_plan=plan,
        )
        ledger = MODULE.build_ledger(
            "fr-meyer/agent-toolkit", 94, [claim], [candidate], [terminal]
        )
        history = ledger["history"]
        self.assertEqual(history["cycle_number"], 1)
        self.assertEqual(history["completed_claim_keys"], [claim["claim_key"]])
        self.assertEqual(history["remediation_source_heads"], [HEAD_SHA])

    def test_pushed_terminal_requires_exact_candidate_and_publish_plan_binding(self):
        claim = make_claim()
        candidate = make_candidate(claim)
        plan = make_publish_plan(claim, candidate)
        terminal = MODULE.terminal_receipt(
            claim,
            "pushed",
            "exact_head_publish_verified",
            result_head_sha=RESULT_SHA,
            publish_plan=plan,
        )
        with self.assertRaisesRegex(
            MODULE.RemediationError, "pushed_terminal_missing_candidate"
        ):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [claim], [], [terminal]
            )

        altered = dict(candidate)
        altered["patch_digest"] = "9" * 64
        with self.assertRaisesRegex(
            MODULE.RemediationError, "terminal_candidate_mismatch"
        ):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [claim], [altered], [terminal]
            )

        invalid_plan = dict(plan)
        invalid_plan["claim_key"] = (
            "fr-meyer/agent-toolkit:94:" + "9" * 40 + ":0"
        )
        with self.assertRaisesRegex(MODULE.RemediationError, "invalid_publish_plan"):
            MODULE.terminal_receipt(
                claim,
                "pushed",
                "exact_head_publish_verified",
                result_head_sha=RESULT_SHA,
                publish_plan=invalid_plan,
            )

    def test_candidate_and_terminal_must_match_their_claim(self):
        claim = make_claim()
        candidate = make_candidate(claim)
        candidate["run_id"] = "999"
        with self.assertRaisesRegex(MODULE.RemediationError, "candidate_claim_mismatch"):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [claim], [candidate], []
            )

        terminal = MODULE.terminal_receipt(
            claim, "provider_failed", "provider_failed"
        )
        terminal["attempt_number"] = 2
        with self.assertRaisesRegex(MODULE.RemediationError, "terminal_claim_mismatch"):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [claim], [], [terminal]
            )

    def test_candidate_metadata_digests_and_attempt_binding_are_required(self):
        claim = make_claim()
        candidate = make_candidate(claim)
        candidate["changed_paths_digest"] = "9" * 64
        with self.assertRaisesRegex(MODULE.RemediationError, "invalid_candidate"):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [claim], [candidate], []
            )

        candidate = make_candidate(claim)
        candidate["attempt_number"] = 2
        with self.assertRaisesRegex(MODULE.RemediationError, "candidate_claim_mismatch"):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [claim], [candidate], []
            )

    def test_claim_attempt_history_must_be_contiguous_and_run_unique(self):
        first = make_claim(attempt=1, run_id="123")
        third = make_claim(attempt=3, run_id="125")
        with self.assertRaisesRegex(
            MODULE.RemediationError, "noncontiguous_attempt_history"
        ):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [first, third], [], []
            )

        second = make_claim(attempt=2, run_id="123")
        with self.assertRaisesRegex(
            MODULE.RemediationError, "duplicate_workflow_run_claim"
        ):
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [first, second], [], []
            )

    def test_artifact_name_must_match_workflow_run_metadata(self):
        original = MODULE.GitHubArtifactClient

        class FakeClient:
            def __init__(self, api_url, token, repository_slug):
                self.repository_slug = repository_slug

            def get(self, path):
                return {
                    "total_count": 1,
                    "artifacts": [
                        {
                            "id": 1,
                            "name": "pullfrog-remediation-claim-pr-94-999-a1",
                            "expired": False,
                            "workflow_run": {"id": 123},
                        }
                    ]
                }

        MODULE.GitHubArtifactClient = FakeClient
        try:
            with self.assertRaisesRegex(MODULE.RemediationError, "invalid_artifact_metadata"):
                MODULE.load_hosted_ledger(
                    api_url="https://api.github.com",
                    token="test",
                    repository_slug="fr-meyer/agent-toolkit",
                    pr_number=94,
                )
        finally:
            MODULE.GitHubArtifactClient = original

    def test_failed_workflow_recovery_is_bounded_by_candidate_and_current_head(self):
        claim = make_claim()
        candidate = make_candidate(claim)

        def load_with(records, current_head):
            original = MODULE.GitHubArtifactClient

            class FakeClient:
                def __init__(self, api_url, token, repository_slug):
                    self.repository_slug = repository_slug

                def get(self, path):
                    if "/actions/artifacts?" in path:
                        return {
                            "total_count": len(records),
                            "artifacts": [
                                {
                                    "id": index,
                                    "name": (
                                        f"pullfrog-remediation-{kind}-pr-94-123-a1"
                                    ),
                                    "expired": False,
                                    "workflow_run": {"id": 123},
                                }
                                for index, kind in enumerate(records, start=1)
                            ]
                        }
                    if path.endswith("/actions/runs/123"):
                        return {
                            "id": 123,
                            "path": MODULE.WORKFLOW_PATH,
                            "status": "completed",
                            "conclusion": "failure",
                        }
                    if path.endswith("/pulls/94"):
                        return pull_request(current_head)
                    raise AssertionError(path)

                def get_bytes(self, path, maximum=MODULE.MAX_ARTIFACT_BYTES):
                    artifact_id = int(path.rsplit("/", 2)[-2])
                    kind = list(records)[artifact_id - 1]
                    filename = {
                        "claim": "claim.json",
                        "candidate": "candidate.json",
                    }[kind]
                    return artifact_zip(filename, records[kind])

            MODULE.GitHubArtifactClient = FakeClient
            try:
                return MODULE.load_hosted_ledger(
                    api_url="https://api.github.com",
                    token="test",
                    repository_slug="fr-meyer/agent-toolkit",
                    pr_number=94,
                )
            finally:
                MODULE.GitHubArtifactClient = original

        no_candidate = load_with({"claim": claim}, HEAD_SHA)
        self.assertEqual(no_candidate["terminals"][0]["status"], "provider_failed")
        self.assertEqual(
            no_candidate["terminals"][0]["code"],
            "recovered_failed_workflow_without_terminal",
        )

        unpublished = load_with({"claim": claim, "candidate": candidate}, HEAD_SHA)
        self.assertEqual(unpublished["terminals"][0]["status"], "publish_failed")

        ambiguous = load_with({"claim": claim, "candidate": candidate}, RESULT_SHA)
        self.assertEqual(ambiguous["terminals"], [])

    def test_artifact_inventory_must_be_complete_and_unexpired(self):
        original = MODULE.GitHubArtifactClient

        class IncompleteClient:
            def __init__(self, api_url, token, repository_slug):
                self.repository_slug = repository_slug

            def get(self, path):
                if "/actions/artifacts?" not in path:
                    raise AssertionError(path)
                page = int(path.rsplit("page=", 1)[1])
                if page == 6:
                    return {
                        "total_count": 501,
                        "artifacts": [
                            {
                                "id": 501,
                                "name": "pullfrog-remediation-claim-pr-94-123-a1",
                                "expired": False,
                                "workflow_run": {"id": 123},
                            }
                        ],
                    }
                artifacts = [
                    {
                        "id": (page - 1) * 100 + index,
                        "name": f"unrelated-{page}-{index}",
                        "expired": False,
                        "workflow_run": {"id": 1},
                    }
                    for index in range(1, 101)
                ]
                return {"total_count": 501, "artifacts": artifacts}

        MODULE.GitHubArtifactClient = IncompleteClient
        try:
            with self.assertRaisesRegex(
                MODULE.RemediationError, "artifact_inventory_incomplete"
            ):
                MODULE.load_hosted_ledger(
                    api_url="https://api.github.com",
                    token="test",
                    repository_slug="fr-meyer/agent-toolkit",
                    pr_number=94,
                )
        finally:
            MODULE.GitHubArtifactClient = original

        class ExpiredClient:
            def __init__(self, api_url, token, repository_slug):
                self.repository_slug = repository_slug

            def get(self, path):
                if "/actions/artifacts?" in path:
                    return {
                        "total_count": 1,
                        "artifacts": [
                            {
                                "id": 1,
                                "name": "pullfrog-remediation-claim-pr-94-123-a1",
                                "expired": True,
                                "workflow_run": {"id": 123},
                            }
                        ],
                    }
                raise AssertionError(path)

        MODULE.GitHubArtifactClient = ExpiredClient
        try:
            with self.assertRaisesRegex(
                MODULE.RemediationError, "expired_remediation_artifact"
            ):
                MODULE.load_hosted_ledger(
                    api_url="https://api.github.com",
                    token="test",
                    repository_slug="fr-meyer/agent-toolkit",
                    pr_number=94,
                )
        finally:
            MODULE.GitHubArtifactClient = original

    def test_history_retention_window_fails_closed(self):
        original = MODULE.GitHubArtifactClient

        class FakeClient:
            def __init__(self, api_url, token, repository_slug):
                self.repository_slug = repository_slug

            def get(self, path):
                if "/actions/artifacts?" in path:
                    return {"total_count": 0, "artifacts": []}
                if path.endswith("/pulls/94"):
                    value = pull_request()
                    value["created_at"] = "2020-01-01T00:00:00Z"
                    return value
                raise AssertionError(path)

        MODULE.GitHubArtifactClient = FakeClient
        try:
            with self.assertRaisesRegex(
                MODULE.RemediationError, "history_retention_window_exceeded"
            ):
                MODULE.load_hosted_ledger(
                    api_url="https://api.github.com",
                    token="test",
                    repository_slug="fr-meyer/agent-toolkit",
                    pr_number=94,
                )
        finally:
            MODULE.GitHubArtifactClient = original

    def test_load_history_emits_coordinator_history_for_cli(self):
        claim = make_claim()
        candidate = make_candidate(claim)
        plan = make_publish_plan(claim, candidate)
        terminal = MODULE.terminal_receipt(
            claim,
            "pushed",
            "exact_head_publish_verified",
            result_head_sha=RESULT_SHA,
            publish_plan=plan,
        )
        ledgers = [
            empty_ledger(),
            MODULE.build_ledger(
                "fr-meyer/agent-toolkit", 94, [claim], [candidate], [terminal]
            ),
        ]
        original_argv = sys.argv
        try:
            for index, ledger in enumerate(ledgers):
                with self.subTest(index=index), tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    ledger_path = root / "ledger.json"
                    history_path = root / "history.json"
                    with mock.patch.object(
                        MODULE, "load_hosted_ledger", return_value=ledger
                    ):
                        sys.argv = [
                            str(SCRIPT),
                            "load-history",
                            "--repository",
                            "fr-meyer/agent-toolkit",
                            "--pr-number",
                            "94",
                            "--out",
                            str(ledger_path),
                            "--history-out",
                            str(history_path),
                        ]
                        self.assertEqual(MODULE.main(), 0)
                    self.assertEqual(
                        json.loads(history_path.read_text(encoding="utf-8")),
                        ledger["history"],
                    )

                    captured = []

                    def stop_after_history(**kwargs):
                        captured.append(kwargs["history"])
                        raise COORDINATOR.CoordinatorError("test_stop")

                    with mock.patch.object(
                        COORDINATOR,
                        "collect_github_snapshot",
                        side_effect=stop_after_history,
                    ):
                        sys.argv = [
                            "pullfrog_cloud_coordinator.py",
                            "evaluate-github",
                            "--repository",
                            "fr-meyer/agent-toolkit",
                            "--pr-number",
                            "94",
                            "--expected-head-sha",
                            HEAD_SHA,
                            "--event-kind",
                            "workflow_dispatch",
                            "--delivery-id",
                            f"dispatch-{index}",
                            "--history",
                            str(history_path),
                            "--out",
                            str(root / "receipt.json"),
                        ]
                        self.assertEqual(COORDINATOR.main(), 0)
                    self.assertEqual(captured, [ledger["history"]])
        finally:
            sys.argv = original_argv

    def test_relative_workspaces_resolve_validator_and_publisher_patches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            (root / "scripts").mkdir()
            source_file = root / "scripts/example.py"
            source_file.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            claim = make_claim(source_head=source)
            source_file.write_text("value = 2\n", encoding="utf-8")
            raw_patch = subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--binary",
                    "--full-index",
                    "--no-renames",
                    source,
                    "--",
                ],
                cwd=root,
            )
            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)

            original_cwd = Path.cwd()
            os.chdir(root.parent)
            try:
                relative = Path(root.name)
                candidate, sealed_patch = MODULE.prepare_candidate_from_patch(
                    claim=claim,
                    workspace=relative,
                    action_outcome="success",
                    action_result_raw=action_result(claim),
                    raw_patch=raw_patch,
                    observed_identity=dict(claim["identity"]),
                )
                subprocess.run(
                    ["git", "reset", "--hard", source], cwd=relative, check=True
                )
                plan = MODULE.apply_candidate(
                    claim=claim,
                    candidate=candidate,
                    patch=sealed_patch,
                    workspace=relative,
                )
            finally:
                os.chdir(original_cwd)
            self.assertEqual(plan["source_head_sha"], source)
            self.assertEqual(source_file.read_text(encoding="utf-8"), "value = 2\n")

    def test_local_candidate_is_flattened_guarded_and_committed_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            (root / "scripts").mkdir()
            source_file = root / "scripts/example.py"
            source_file.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            claim = make_claim(source_head=source)
            observed = dict(claim["identity"])

            source_file.write_text("value = 2\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "agent local commit"], cwd=root, check=True)
            candidate, patch = MODULE.prepare_candidate(
                claim=claim,
                workspace=root,
                action_outcome="success",
                action_result_raw=action_result(claim),
                observed_identity=observed,
            )
            self.assertEqual(candidate["changed_paths"], ["scripts/example.py"])
            self.assertEqual(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), source)

            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)
            plan = MODULE.apply_candidate(
                claim=claim,
                candidate=candidate,
                patch=patch,
                workspace=root,
            )
            self.assertEqual(plan["source_head_sha"], source)
            self.assertEqual(plan["claim_key"], claim["claim_key"])
            self.assertEqual(plan["candidate_digest"], MODULE._digest(candidate))
            self.assertEqual(
                MODULE._validate_publish_plan(plan, claim, candidate), plan
            )
            altered_candidate = dict(candidate)
            altered_candidate["action_result_digest"] = "9" * 64
            with self.assertRaisesRegex(
                MODULE.RemediationError, "publish_plan_candidate_mismatch"
            ):
                MODULE._validate_publish_plan(plan, claim, altered_candidate)
            parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=root, text=True).strip()
            self.assertEqual(parent, source)
            self.assertEqual(source_file.read_text(encoding="utf-8"), "value = 2\n")
            self.assertEqual(
                subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True),
                "",
            )

    def test_raw_provider_patch_is_rebuilt_in_a_fresh_trusted_checkout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            (root / "scripts").mkdir()
            source_file = root / "scripts/example.py"
            source_file.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            claim = make_claim(source_head=source)
            source_file.write_text("value = 2\n", encoding="utf-8")
            raw_patch = subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--binary",
                    "--full-index",
                    "--no-renames",
                    source,
                    "--",
                ],
                cwd=root,
            )
            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)

            candidate, sealed_patch = MODULE.prepare_candidate_from_patch(
                claim=claim,
                workspace=root,
                action_outcome="success",
                action_result_raw=action_result(claim),
                raw_patch=raw_patch,
                observed_identity=dict(claim["identity"]),
            )
            self.assertEqual(candidate["changed_paths"], ["scripts/example.py"])
            self.assertEqual(candidate["patch_digest"], MODULE._bytes_digest(sealed_patch))
            self.assertEqual(
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=root, text=True
                ).strip(),
                source,
            )
            self.assertEqual(
                subprocess.check_output(
                    ["git", "diff", "--cached", "--name-only"], cwd=root, text=True
                ).strip(),
                "scripts/example.py",
            )

    def test_non_dev_base_policy_reaches_claim_validator_and_publisher(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            (root / "scripts").mkdir()
            source_file = root / "scripts/example.py"
            source_file.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()

            receipt = remediation_receipt(head_sha=source, base_ref="staging")
            decision, claim = MODULE.prepare_claim(
                receipt, empty_ledger(), run_id="123", run_attempt=1
            )
            self.assertEqual(decision["status"], "ready")
            self.assertIsNotNone(claim)
            assert claim is not None
            self.assertEqual(
                claim["destination_policy"],
                {
                    "default_branch": "main",
                    "protected_refs": ["dev", "main", "staging"],
                },
            )

            source_file.write_text("value = 2\n", encoding="utf-8")
            raw_patch = subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--binary",
                    "--full-index",
                    "--no-renames",
                    source,
                    "--",
                ],
                cwd=root,
            )
            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)
            candidate, sealed_patch = MODULE.prepare_candidate_from_patch(
                claim=claim,
                workspace=root,
                action_outcome="success",
                action_result_raw=action_result(claim),
                raw_patch=raw_patch,
                observed_identity=dict(claim["identity"]),
            )
            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)
            plan = MODULE.apply_candidate(
                claim=claim,
                candidate=candidate,
                patch=sealed_patch,
                workspace=root,
            )
            self.assertEqual(plan["source_head_sha"], source)
            self.assertEqual(plan["destination_guard"]["status"], "allowed")

    def test_raw_provider_patch_cannot_touch_forbidden_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            claim = make_claim(source_head=source)
            forbidden = root / ".github/workflows/unsafe.yml"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("name: unsafe\n", encoding="utf-8")
            subprocess.run(["git", "add", "-N", "--", str(forbidden)], cwd=root, check=True)
            raw_patch = subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--binary",
                    "--full-index",
                    "--no-renames",
                    source,
                    "--",
                ],
                cwd=root,
            )
            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)
            with self.assertRaisesRegex(
                MODULE.RemediationError, "candidate_destination_blocked"
            ):
                MODULE.prepare_candidate_from_patch(
                    claim=claim,
                    workspace=root,
                    action_outcome="success",
                    action_result_raw=action_result(claim),
                    raw_patch=raw_patch,
                    observed_identity=dict(claim["identity"]),
                )

    def test_validator_authority_patch_is_rejected_before_sealing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            validator = root / "scripts/github/speculoos_pr_contract.py"
            validator.parent.mkdir(parents=True)
            validator.write_text("raise SystemExit(1)\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            claim = make_claim(source_head=source)
            validator.write_text("raise SystemExit(0)\n", encoding="utf-8")
            raw_patch = subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--binary",
                    "--full-index",
                    "--no-renames",
                    source,
                    "--",
                ],
                cwd=root,
            )
            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)
            with self.assertRaisesRegex(
                MODULE.RemediationError, "candidate_destination_blocked"
            ):
                MODULE.prepare_candidate_from_patch(
                    claim=claim,
                    workspace=root,
                    action_outcome="success",
                    action_result_raw=action_result(claim),
                    raw_patch=raw_patch,
                    observed_identity=dict(claim["identity"]),
                )

    def test_publisher_rechecks_validator_authority_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            validator = root / "scripts/github/speculoos_pr_contract.py"
            validator.parent.mkdir(parents=True)
            validator.write_text("raise SystemExit(1)\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            claim = make_claim(source_head=source)
            validator.write_text("raise SystemExit(0)\n", encoding="utf-8")
            patch = subprocess.check_output(
                [
                    "git",
                    "diff",
                    "--binary",
                    "--full-index",
                    "--no-renames",
                    source,
                    "--",
                ],
                cwd=root,
            )
            subprocess.run(["git", "reset", "--hard", source], cwd=root, check=True)
            changed_paths = ["scripts/github/speculoos_pr_contract.py"]
            candidate = {
                "schema": MODULE.CANDIDATE_SCHEMA,
                "run_id": claim["run_id"],
                "attempt_id": claim["attempt_id"],
                "claim_key": claim["claim_key"],
                "cycle_number": claim["cycle_number"],
                "attempt_number": claim["attempt_number"],
                "source_head_sha": source,
                "patch_digest": MODULE._bytes_digest(patch),
                "patch_bytes": len(patch),
                "changed_paths": changed_paths,
                "changed_paths_digest": MODULE._digest(changed_paths),
                "action_result_digest": "a" * 64,
                "destination_guard": {"status": "allowed"},
            }
            with self.assertRaisesRegex(
                MODULE.RemediationError, "publish_destination_blocked"
            ):
                MODULE.apply_candidate(
                    claim=claim,
                    candidate=candidate,
                    patch=patch,
                    workspace=root,
                )

    def test_forbidden_post_patch_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
            )
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            claim = make_claim(source_head=source)
            forbidden = root / ".github/workflows/unsafe.yml"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("name: unsafe\n", encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.RemediationError, "candidate_destination_blocked"
            ):
                MODULE.prepare_candidate(
                    claim=claim,
                    workspace=root,
                    action_outcome="success",
                    action_result_raw=action_result(claim),
                    observed_identity=dict(claim["identity"]),
                )

    def test_action_failure_never_creates_a_candidate(self):
        claim = make_claim()
        with self.assertRaisesRegex(MODULE.RemediationError, "provider_failed"):
            MODULE.prepare_candidate(
                claim=claim,
                workspace=Path("/nonexistent"),
                action_outcome="failure",
                action_result_raw="",
                observed_identity=dict(claim["identity"]),
            )

        for outcome in ("candidate_patch_too_large", "action_result_too_large"):
            with self.subTest(outcome=outcome):
                with self.assertRaisesRegex(MODULE.RemediationError, outcome):
                    MODULE.prepare_candidate_from_patch(
                        claim=claim,
                        workspace=Path("/nonexistent"),
                        action_outcome=outcome,
                        action_result_raw="",
                        raw_patch=b"",
                        observed_identity=dict(claim["identity"]),
                    )


if __name__ == "__main__":
    unittest.main()
