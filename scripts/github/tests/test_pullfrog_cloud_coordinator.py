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

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_cloud_coordinator.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_cloud_coordinator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
NEXT_SHA = "3" * 40


def pull_request(head_sha=HEAD_SHA, head_repo="fr-meyer/agent-toolkit", state="open"):
    return {
        "number": 94,
        "state": state,
        "base": {"ref": "dev", "sha": BASE_SHA},
        "head": {
            "ref": "chore/pullfrog-full-automation",
            "sha": head_sha,
            "repo": {"full_name": head_repo},
        },
    }


def check(name, conclusion="success", app="pullfrog", check_id=100, suite_id=50, head_sha=HEAD_SHA):
    return {
        "id": check_id,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": head_sha,
        "app": {"slug": app},
        "check_suite": {"id": suite_id},
    }


def base_snapshot(with_findings=False):
    approval = "failure" if with_findings else "success"
    review_body = (
        "One exact-head issue" if with_findings else "No new issues found"
    ) + "\n<!-- PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ -->"
    comments = []
    if with_findings:
        comments = [
            {
                "id": 701,
                "pull_request_review_id": 601,
                "commit_id": HEAD_SHA,
                "path": "scripts/example.py",
                "line": 12,
                "body": "Do not trust a stale event head.",
                "user": {"login": "pullfrog[bot]"},
            }
        ]
    return {
        "schema": MODULE.SNAPSHOT_SCHEMA,
        "repository_slug": "fr-meyer/agent-toolkit",
        "repository": {"default_branch": "main"},
        "event": {
            "kind": "pullfrog_review_completed",
            "delivery_id": "check-run:100",
            "head_sha": HEAD_SHA,
        },
        "expected_pull_request": pull_request(),
        "observed_pull_request": pull_request(),
        "reviews": [
            {
                "id": 601,
                "commit_id": HEAD_SHA,
                "submitted_at": "2026-10-27T10:00:00Z",
                "state": "COMMENTED",
                "body": review_body,
                "user": {"login": "pullfrog[bot]"},
            }
        ],
        "review_comments": comments,
        "review_threads": [
            {
                "isResolved": not with_findings,
                "isOutdated": False,
                "path": "scripts/example.py",
                "line": 12,
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 701,
                            "author": {"login": "pullfrog[bot]"},
                            "pullRequestReview": {"databaseId": 601},
                        }
                    ]
                },
            }
        ],
        "files": [
            {"filename": "scripts/example.py"},
            {"filename": "docs/example.md"},
        ],
        "check_runs": [
            check("pullfrog", check_id=100),
            check("pullfrog-approval", approval, check_id=101),
            check("ci-required", app="github-actions", check_id=102, suite_id=60),
            check("speculoos", app="github-actions", check_id=103, suite_id=61),
        ],
        "history": MODULE._empty_history(),
        "policy": {
            "max_cycles": 3,
            "protected_refs": ["dev", "main"],
            "ci_checks": [{"name": "ci-required", "app_slug": "github-actions"}],
            "speculoos_checks": [{"name": "speculoos", "app_slug": "github-actions"}],
        },
    }


class PullfrogCloudCoordinatorTests(unittest.TestCase):
    def test_clean_exact_head_is_reported_without_mutation(self):
        receipt = MODULE.evaluate_snapshot(base_snapshot())
        self.assertEqual(receipt["status"], "clean")
        self.assertEqual(receipt["would_action"], "complete")
        self.assertEqual(receipt["executed_action"], "none")
        self.assertFalse(receipt["mutation"]["enabled"])
        self.assertFalse(any(receipt["mutation"].values()))

    def test_live_base_and_default_are_always_protected_during_collection(self):
        fixture = base_snapshot()
        for key in ("expected_pull_request", "observed_pull_request"):
            fixture[key]["base"]["ref"] = "staging"

        class StubClient:
            repository_slug = "fr-meyer/agent-toolkit"

            def get(self, path):
                prefix = "/repos/fr-meyer/agent-toolkit"
                if path == prefix:
                    return {"default_branch": "main"}
                if path == f"{prefix}/pulls/94":
                    return copy.deepcopy(fixture["expected_pull_request"])
                if path == f"{prefix}/commits/{HEAD_SHA}/check-runs?per_page=100":
                    return {
                        "total_count": len(fixture["check_runs"]),
                        "check_runs": copy.deepcopy(fixture["check_runs"]),
                    }
                raise AssertionError(path)

            def paginated(self, path):
                suffix = path.rsplit("/", 1)[-1]
                mapping = {
                    "reviews": fixture["reviews"],
                    "comments": fixture["review_comments"],
                    "files": fixture["files"],
                }
                if suffix not in mapping:
                    raise AssertionError(path)
                return copy.deepcopy(mapping[suffix])

            def graphql(self, query, variables):
                return {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": copy.deepcopy(fixture["review_threads"]),
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                }
                            }
                        }
                    }
                }

        with mock.patch.object(MODULE, "GitHubReadClient", return_value=StubClient()):
            snapshot = MODULE.collect_github_snapshot(
                api_url="https://api.github.com",
                token="test-token",
                repository_slug="fr-meyer/agent-toolkit",
                pr_number=94,
                expected_head_sha=HEAD_SHA,
                event_kind="pullfrog_review_completed",
                delivery_id="check-run:100",
                protected_refs=["main", "master"],
                ci_rules=[{"name": "ci-required", "app_slug": "github-actions"}],
                speculoos_rules=[
                    {"name": "speculoos", "app_slug": "github-actions"}
                ],
                history=MODULE._empty_history(),
            )
        self.assertEqual(
            snapshot["policy"]["protected_refs"], ["main", "master", "staging"]
        )
        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["status"], "clean")
        self.assertEqual(
            receipt["destination_policy"],
            {
                "default_branch": "main",
                "protected_refs": ["main", "master", "staging"],
            },
        )

    def test_findings_report_would_remediate_but_execute_nothing(self):
        receipt = MODULE.evaluate_snapshot(base_snapshot(with_findings=True))
        self.assertEqual(receipt["status"], "remediation_ready")
        self.assertEqual(receipt["would_action"], "start_remediation")
        self.assertEqual(receipt["executed_action"], "none")
        self.assertEqual(receipt["cycle_decision"]["review"]["finding_count"], 1)
        self.assertFalse(any(receipt["mutation"].values()))

    def test_third_cycle_allows_clean_completion_but_never_a_fourth_remediation(self):
        for with_findings, expected_status, expected_blocker in (
            (False, "clean", None),
            (True, "stopped", "cycle_limit_exhausted"),
        ):
            with self.subTest(with_findings=with_findings):
                snapshot = base_snapshot(with_findings=with_findings)
                snapshot["history"] = {
                    "schema": MODULE.HISTORY_SCHEMA,
                    "cycle_number": 3,
                    "completed_claim_keys": [
                        f"fr-meyer/agent-toolkit:94:{value * 40}:{index}"
                        for index, value in enumerate(("3", "4", "5"))
                    ],
                    "remediation_source_heads": ["3" * 40, "4" * 40, "5" * 40],
                    "finding_set_digests": ["a" * 64, "b" * 64, "c" * 64],
                    "output_digests": ["d" * 64, "e" * 64, "f" * 64],
                }
                receipt = MODULE.evaluate_snapshot(snapshot)
                self.assertEqual(receipt["status"], expected_status)
                self.assertEqual(receipt["destination_guard"]["status"], "allowed")
                if expected_blocker:
                    self.assertIn(
                        expected_blocker, receipt["cycle_decision"]["blockers"]
                    )
                else:
                    self.assertEqual(receipt["would_action"], "complete")
                    self.assertEqual(receipt["cycle_decision"]["blockers"], [])

    def test_review_and_comment_text_never_reach_receipt(self):
        snapshot = base_snapshot(with_findings=True)
        snapshot["reviews"][0]["body"] = "PRIVATE REVIEW TEXT"
        snapshot["review_comments"][0]["body"] = "PRIVATE COMMENT TEXT"
        rendered = json.dumps(MODULE.evaluate_snapshot(snapshot), sort_keys=True)
        self.assertNotIn("PRIVATE REVIEW TEXT", rendered)
        self.assertNotIn("PRIVATE COMMENT TEXT", rendered)
        self.assertNotIn("Do not trust", rendered)

    def test_missing_speculoos_fails_closed(self):
        snapshot = base_snapshot()
        snapshot["check_runs"] = [
            item for item in snapshot["check_runs"] if item["name"] != "speculoos"
        ]
        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("check_speculoos_missing", receipt["cycle_decision"]["blockers"])
        self.assertEqual(receipt["would_action"], "none")

    def test_failed_cancelled_timed_out_and_pending_ci_fail_closed(self):
        variants = {
            "failure": ("completed", "failure"),
            "cancelled": ("completed", "cancelled"),
            "timed_out": ("completed", "timed_out"),
            "pending": ("in_progress", None),
        }
        for expected, (status, conclusion) in variants.items():
            with self.subTest(expected=expected):
                snapshot = base_snapshot()
                ci = next(item for item in snapshot["check_runs"] if item["name"] == "ci-required")
                ci["status"] = status
                ci["conclusion"] = conclusion
                receipt = MODULE.evaluate_snapshot(snapshot)
                self.assertEqual(receipt["status"], "stopped")
                self.assertIn(
                    f"check_ci_{expected}", receipt["cycle_decision"]["blockers"]
                )

    def test_stale_event_and_head_drift_fail_closed(self):
        snapshot = base_snapshot()
        snapshot["event"]["head_sha"] = NEXT_SHA
        snapshot["observed_pull_request"] = pull_request(head_sha=NEXT_SHA)
        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("head_sha_drift", receipt["cycle_decision"]["blockers"])

    def test_fork_and_forbidden_governance_path_fail_closed(self):
        fork = base_snapshot()
        fork["expected_pull_request"] = pull_request(head_repo="fork/agent-toolkit")
        fork["observed_pull_request"] = pull_request(head_repo="fork/agent-toolkit")
        fork_receipt = MODULE.evaluate_snapshot(fork)
        self.assertIn("fork_head_forbidden", fork_receipt["destination_guard"]["blockers"])
        self.assertEqual(fork_receipt["status"], "stopped")

        workflow = base_snapshot(with_findings=True)
        workflow["files"] = [{"filename": ".github/workflows/unsafe.yml"}]
        workflow_receipt = MODULE.evaluate_snapshot(workflow)
        self.assertIn(
            "forbidden_changed_path", workflow_receipt["destination_guard"]["blockers"]
        )
        self.assertEqual(workflow_receipt["would_action"], "none")

    def test_wrong_app_cannot_spoof_pullfrog_or_required_checks(self):
        snapshot = base_snapshot()
        snapshot["check_runs"] = [
            {**item, "app": {"slug": "github-actions"}}
            if item["name"] in {"pullfrog", "pullfrog-approval"}
            else item
            for item in snapshot["check_runs"]
        ]
        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["checks"]["pullfrog"]["status"], "missing")
        self.assertGreater(receipt["checks"]["pullfrog"]["spoofed_count"], 0)
        self.assertEqual(receipt["status"], "stopped")

    def test_spoofed_or_stale_duplicate_check_stops_even_with_valid_check(self):
        spoofed = base_snapshot()
        spoofed["check_runs"].append(
            check(
                "ci-required",
                app="untrusted-app",
                check_id=500,
                suite_id=500,
            )
        )
        spoofed_receipt = MODULE.evaluate_snapshot(spoofed)
        self.assertEqual(spoofed_receipt["status"], "stopped")
        self.assertIn("ci_check_spoofed", spoofed_receipt["coordinator_blockers"])

        stale = base_snapshot()
        stale["check_runs"].append(
            check(
                "speculoos",
                app="github-actions",
                check_id=501,
                suite_id=501,
                head_sha=BASE_SHA,
            )
        )
        stale_receipt = MODULE.evaluate_snapshot(stale)
        self.assertEqual(stale_receipt["status"], "stopped")
        self.assertIn(
            "speculoos_check_stale", stale_receipt["coordinator_blockers"]
        )

    def test_latest_exact_app_check_supersedes_older_result(self):
        snapshot = base_snapshot()
        snapshot["check_runs"].append(
            check("ci-required", "failure", app="github-actions", check_id=90, suite_id=59)
        )
        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["status"], "clean")
        self.assertEqual(receipt["checks"]["ci"][0]["check_run_id"], 102)
        self.assertEqual(receipt["checks"]["ci"][0]["superseded_count"], 1)

    def test_pullfrog_checks_must_share_a_suite(self):
        snapshot = base_snapshot()
        approval = next(
            item for item in snapshot["check_runs"] if item["name"] == "pullfrog-approval"
        )
        approval["check_suite"]["id"] = 999
        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("pullfrog_check_suite_mismatch", receipt["coordinator_blockers"])

    def test_duplicate_claim_is_an_idempotent_noop(self):
        snapshot = base_snapshot(with_findings=True)
        claim = f"fr-meyer/agent-toolkit:94:{HEAD_SHA}:0"
        snapshot["history"]["completed_claim_keys"] = [claim]
        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["status"], "duplicate")
        self.assertEqual(receipt["would_action"], "none")
        self.assertEqual(receipt["executed_action"], "none")

    def test_repeated_semantic_findings_ignore_volatile_github_ids(self):
        first = MODULE.evaluate_snapshot(base_snapshot(with_findings=True))
        snapshot = base_snapshot(with_findings=True)
        snapshot["event"] = {
            "kind": "pullfrog_review_completed",
            "delivery_id": "check-run:200",
            "head_sha": NEXT_SHA,
        }
        snapshot["expected_pull_request"] = pull_request(head_sha=NEXT_SHA)
        snapshot["observed_pull_request"] = pull_request(head_sha=NEXT_SHA)
        snapshot["reviews"][0].update(
            {
                "id": 602,
                "commit_id": NEXT_SHA,
                "submitted_at": "2026-10-27T11:00:00Z",
                "body": "  ONE exact-head issue  \n<!-- PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ -->",
            }
        )
        snapshot["review_comments"][0].update(
            {
                "id": 999,
                "pull_request_review_id": 602,
                "commit_id": NEXT_SHA,
                "body": "  DO NOT trust a stale event head.  ",
            }
        )
        for index, item in enumerate(snapshot["check_runs"], start=200):
            item["id"] = index
            item["head_sha"] = NEXT_SHA
        snapshot["history"] = {
            "schema": MODULE.HISTORY_SCHEMA,
            "cycle_number": 1,
            "completed_claim_keys": [
                f"fr-meyer/agent-toolkit:94:{HEAD_SHA}:0"
            ],
            "remediation_source_heads": [HEAD_SHA],
            "finding_set_digests": [
                first["cycle_decision"]["review"]["finding_set_digest"]
            ],
            "output_digests": [
                first["cycle_decision"]["review"]["output_digest"]
            ],
        }

        receipt = MODULE.evaluate_snapshot(snapshot)
        self.assertEqual(receipt["status"], "stopped")
        self.assertIn("repeated_findings", receipt["cycle_decision"]["blockers"])
        self.assertIn("unchanged_output", receipt["cycle_decision"]["blockers"])

    def test_stale_or_malformed_selected_review_comment_fails_closed(self):
        stale = base_snapshot(with_findings=True)
        stale["review_comments"][0]["commit_id"] = BASE_SHA
        stale_receipt = MODULE.evaluate_snapshot(stale)
        self.assertEqual(stale_receipt["status"], "stopped")
        self.assertIn(
            "stale_pullfrog_review_comment", stale_receipt["coordinator_blockers"]
        )

        malformed = base_snapshot(with_findings=True)
        malformed["review_comments"][0]["body"] = ""
        malformed_receipt = MODULE.evaluate_snapshot(malformed)
        self.assertEqual(malformed_receipt["status"], "stopped")
        self.assertIn(
            "invalid_pullfrog_review_comment", malformed_receipt["coordinator_blockers"]
        )

    def test_event_resolver_accepts_only_one_exact_pr(self):
        event = {
            "check_run": {
                "id": 12,
                "head_sha": HEAD_SHA,
                "pull_requests": [{"number": 94}],
            }
        }
        context = MODULE.resolve_event_context("check_run", event, "", "", "123")
        self.assertEqual(context["pr_number"], 94)
        self.assertEqual(context["event_kind"], "pullfrog_review_completed")

        event["check_run"]["pull_requests"].append({"number": 95})
        with self.assertRaisesRegex(MODULE.CoordinatorError, "invalid_event_context"):
            MODULE.resolve_event_context("check_run", event, "", "", "123")

        event["check_run"]["pull_requests"] = [{"number": 94}]
        event["check_run"]["id"] = 0
        with self.assertRaisesRegex(MODULE.CoordinatorError, "invalid_event_id"):
            MODULE.resolve_event_context("check_run", event, "", "", "123")

    def test_github_client_uses_get_and_rejects_foreign_paths(self):
        client = MODULE.GitHubReadClient(
            "https://api.github.com", "not-a-real-token", "fr-meyer/agent-toolkit"
        )
        response = mock.MagicMock()
        response.read.return_value = b'{"ok": true}'
        response.__enter__.return_value = response
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            self.assertEqual(client.get("/repos/fr-meyer/agent-toolkit"), {"ok": True})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertNotIn("not-a-real-token", request.full_url)
        with self.assertRaisesRegex(MODULE.CoordinatorError, "forbidden_github_api_path"):
            client.get("/repos/another/repository")
        with self.assertRaisesRegex(MODULE.CoordinatorError, "forbidden_github_api_path"):
            client.get("/repos/fr-meyer/agent-toolkit-evil")

    def test_cli_is_deterministic_and_failure_receipt_is_sanitized(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snapshot_path = root / "snapshot.json"
            first = root / "first.json"
            second = root / "second.json"
            snapshot_path.write_text(json.dumps(base_snapshot()), encoding="utf-8")
            for out in (first, second):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "evaluate-snapshot",
                        "--snapshot",
                        str(snapshot_path),
                        "--out",
                        str(out),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "secret-value"}, clear=False):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "evaluate-github",
                        "--repository",
                        "bad slug",
                        "--pr-number",
                        "94",
                        "--expected-head-sha",
                        HEAD_SHA,
                        "--event-kind",
                        "workflow_dispatch",
                        "--delivery-id",
                        "dispatch-1",
                        "--out",
                        str(first),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    env={**os.environ, "GITHUB_TOKEN": "secret-value"},
                )
            self.assertEqual(json.loads(first.read_text())["status"], "stopped")
            self.assertNotIn("secret-value", first.read_text())

            event_path = root / "event.json"
            output_path = root / "github-output"
            failure_receipt = root / "event-failure.json"
            event_path.write_text(
                json.dumps(
                    {
                        "check_run": {
                            "id": 0,
                            "head_sha": HEAD_SHA,
                            "pull_requests": [{"number": 94}],
                        }
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "resolve-event",
                    "--event",
                    str(event_path),
                    "--event-name",
                    "check_run",
                    "--run-id",
                    "123",
                    "--github-output",
                    str(output_path),
                    "--failure-receipt",
                    str(failure_receipt),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            failure = json.loads(failure_receipt.read_text())
            self.assertEqual(failure["status"], "stopped")
            self.assertEqual(failure["coordinator_blockers"], ["invalid_event_id"])
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
