import copy
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_dev_auto_merge.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_dev_auto_merge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
MERGE_SHA = "3" * 40


def check_run(check_id, name, app_slug, *, status="success", suite_id=900):
    return {
        "id": check_id,
        "name": name,
        "head_sha": HEAD_SHA,
        "status": "completed" if status != "pending" else "in_progress",
        "conclusion": status if status != "pending" else None,
        "app": {"slug": app_slug},
        "check_suite": {"id": suite_id},
    }


def clean_receipt():
    repository = {
        "slug": "fr-meyer/agent-toolkit",
        "pr_number": 95,
        "base_ref": "dev",
        "base_sha": BASE_SHA,
        "head_ref": "feat/pullfrog-write-capable-loop",
        "head_sha": HEAD_SHA,
        "head_repository_slug": "fr-meyer/agent-toolkit",
    }
    observed = {
        name: {"status": "success", "head_sha": HEAD_SHA}
        for name in MODULE.REQUIRED_CHECKS
    }
    check_details = {
        "pullfrog": [
            {
                "name": "pullfrog",
                "app_slug": "pullfrog",
                "status": "success",
                "head_sha": HEAD_SHA,
                "check_run_id": 101,
                "check_suite_id": 900,
            }
        ],
        "pullfrog_approval": [
            {
                "name": "pullfrog-approval",
                "app_slug": "pullfrog",
                "status": "success",
                "head_sha": HEAD_SHA,
                "check_run_id": 102,
                "check_suite_id": 900,
            }
        ],
        "ci": [
            {
                "name": "dogfood / Provider-free PR automation contract",
                "app_slug": "github-actions",
                "status": "success",
                "head_sha": HEAD_SHA,
                "check_run_id": 103,
                "check_suite_id": 901,
            }
        ],
        "speculoos": [
            {
                "name": "speculoos",
                "app_slug": "github-actions",
                "status": "success",
                "head_sha": HEAD_SHA,
                "check_run_id": 104,
                "check_suite_id": 902,
            }
        ],
    }
    changed_paths = ["scripts/example.py"]
    return {
        "schema": MODULE.COORDINATOR_SCHEMA,
        "mode": "dry-run",
        "status": "clean",
        "would_action": "complete",
        "executed_action": "none",
        "coordinator_blockers": [],
        "mutation": {
            "enabled": False,
            "attempted": False,
            "repository_write": False,
            "provider_invocation": False,
            "approval": False,
            "merge": False,
            "rerun": False,
            "release": False,
            "deployment": False,
            "settings_change": False,
            "branch_deletion": False,
        },
        "identity": {
            "repository_slug": repository["slug"],
            "pr_number": repository["pr_number"],
            "base_ref": repository["base_ref"],
            "base_sha": repository["base_sha"],
            "head_ref": repository["head_ref"],
            "head_sha": repository["head_sha"],
            "head_repository_slug": repository["head_repository_slug"],
            "event_head_sha": repository["head_sha"],
        },
        "collection": {
            "changed_paths_count": len(changed_paths),
            "changed_paths_digest": MODULE._digest(changed_paths),
        },
        "checks": check_details,
        "destination_guard": {
            "status": "allowed",
            "blockers": [],
            "destination": {
                "repository_slug": repository["slug"],
                "ref": repository["head_ref"],
                "sha": repository["head_sha"],
                "attempt": 1,
            },
        },
        "cycle_decision": {
            "schema": MODULE.cycle_contract.DECISION_SCHEMA,
            "status": "clean",
            "action": "complete",
            "blockers": [],
            "repository": repository,
            "event": {"head_sha": HEAD_SHA},
            "review": {
                "head_sha": HEAD_SHA,
                "finding_count": 0,
                "review_id": "700",
            },
            "evidence": {
                "required_checks": sorted(MODULE.REQUIRED_CHECKS),
                "missing_checks": [],
                "observed_checks": observed,
            },
        },
    }


def receipt_for_paths(paths):
    receipt = clean_receipt()
    normalized = sorted(paths)
    receipt["collection"] = {
        "changed_paths_count": len(normalized),
        "changed_paths_digest": MODULE._digest(normalized),
    }
    return receipt


class FakeClient:
    def __init__(self):
        self.allowed_prefix = "/repos/fr-meyer/agent-toolkit"
        self.pr = {
            "number": 95,
            "state": "open",
            "draft": False,
            "title": "Guarded Pullfrog loop",
            "base": {"ref": "dev", "sha": BASE_SHA},
            "head": {
                "ref": "feat/pullfrog-write-capable-loop",
                "sha": HEAD_SHA,
                "repo": {"full_name": "fr-meyer/agent-toolkit"},
            },
        }
        self.repository = {"default_branch": "main"}
        self.reviews = [
            {
                "id": 700,
                "state": "COMMENTED",
                "body": "No new issues found.",
                "commit_id": HEAD_SHA,
                "submitted_at": "2026-10-28T00:00:00Z",
                "user": {"login": "pullfrog[bot]"},
            }
        ]
        self.comments = []
        self.files = [{"filename": "scripts/example.py"}]
        self.check_runs = [
            check_run(101, "pullfrog", "pullfrog", suite_id=900),
            check_run(102, "pullfrog-approval", "pullfrog", suite_id=900),
            check_run(
                103,
                "dogfood / Provider-free PR automation contract",
                "github-actions",
                suite_id=901,
            ),
            check_run(104, "speculoos", "github-actions", suite_id=902),
        ]
        self.refs = {"dev": BASE_SHA, "main": "9" * 40, "master": "8" * 40}
        self.merge_result = {
            "merged": True,
            "sha": MERGE_SHA,
            "base_ref": "dev",
            "base_sha": BASE_SHA,
            "head_sha": HEAD_SHA,
            "transport": "normal-fast-forward-push",
        }
        self.push_calls = []
        self.before_push = None
        self.dispatch_calls = []
        self.dispatch_failure = False

    def get(self, path):
        if path == self.allowed_prefix:
            return copy.deepcopy(self.repository)
        if path == f"{self.allowed_prefix}/pulls/95":
            return copy.deepcopy(self.pr)
        if path == f"{self.allowed_prefix}/commits/{HEAD_SHA}/check-runs?per_page=100":
            return {
                "total_count": len(self.check_runs),
                "check_runs": copy.deepcopy(self.check_runs),
            }
        raise AssertionError(path)

    def paginated(self, path):
        if path == f"{self.allowed_prefix}/pulls/95/reviews":
            return copy.deepcopy(self.reviews)
        if path == f"{self.allowed_prefix}/pulls/95/comments":
            return copy.deepcopy(self.comments)
        if path == f"{self.allowed_prefix}/pulls/95/files":
            return copy.deepcopy(self.files)
        raise AssertionError(path)

    def push_exact_merge(self, identity, title):
        if self.before_push is not None:
            self.before_push(self)
        self.push_calls.append((copy.deepcopy(identity), title))
        if self.refs.get(identity["base_ref"]) != identity["base_sha"]:
            raise MODULE.AutoMergeError("base_compare_and_swap_failed")
        self.refs[identity["base_ref"]] = MERGE_SHA
        return copy.deepcopy(self.merge_result)

    def dispatch_workflow(self, workflow, *, ref, inputs):
        self.dispatch_calls.append((workflow, ref, copy.deepcopy(inputs)))
        if self.dispatch_failure:
            raise MODULE.AutoMergeError("workflow_dispatch_failed")


class PullfrogDevAutoMergeTests(unittest.TestCase):
    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(MODULE.AutoMergeError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_clean_exact_head_dev_pr_merges_once(self):
        client = FakeClient()
        result = MODULE.merge_clean_dev_pr(client, clean_receipt(), expected_head_sha=HEAD_SHA)
        self.assertEqual(result["status"], "merged")
        self.assertEqual(result["base_ref"], "dev")
        self.assertEqual(result["head_sha"], HEAD_SHA)
        self.assertEqual(result["merge_commit_sha"], MERGE_SHA)
        self.assertEqual(result["merge_method"], "merge")
        self.assertEqual(result["merge_transport"], "normal-fast-forward-push")
        self.assertFalse(result["branch_deleted"])
        self.assertEqual(len(client.push_calls), 1)
        self.assertEqual(result["downstream_dispatches"], [])
        self.assertEqual(result["downstream_dispatch_failures"], [])

    def test_main_and_master_bases_fail_closed(self):
        for base in ("main", "master"):
            with self.subTest(base=base):
                receipt = clean_receipt()
                receipt["identity"]["base_ref"] = base
                receipt["cycle_decision"]["repository"]["base_ref"] = base
                self.assert_code(
                    "ineligible_identity", MODULE.validate_clean_receipt, receipt
                )

    def test_forks_and_unapproved_head_prefixes_fail_closed(self):
        for field, value in (
            ("head_repository_slug", "someone/fork"),
            ("head_ref", "release/v1"),
        ):
            with self.subTest(field=field):
                receipt = clean_receipt()
                receipt["identity"][field] = value
                receipt["cycle_decision"]["repository"][field] = value
                if field == "head_repository_slug":
                    receipt["destination_guard"]["destination"]["repository_slug"] = value
                else:
                    receipt["destination_guard"]["destination"]["ref"] = value
                self.assert_code(
                    "ineligible_identity", MODULE.validate_clean_receipt, receipt
                )

    def test_missing_or_failed_required_evidence_fails_closed(self):
        receipt = clean_receipt()
        receipt["cycle_decision"]["evidence"]["observed_checks"]["speculoos"][
            "status"
        ] = "failure"
        self.assert_code(
            "required_evidence_not_successful", MODULE.validate_clean_receipt, receipt
        )

        receipt = clean_receipt()
        receipt["cycle_decision"]["evidence"]["required_checks"].remove("speculoos")
        self.assert_code("invalid_clean_decision", MODULE.validate_clean_receipt, receipt)

    def test_live_head_base_and_repository_drift_fail_closed(self):
        variants = (
            ("head", "sha", "4" * 40),
            ("base", "sha", "5" * 40),
            ("base", "ref", "main"),
            ("head", "ref", "release/v1"),
        )
        for section, key, value in variants:
            with self.subTest(section=section, key=key):
                client = FakeClient()
                client.pr[section][key] = value
                self.assert_code(
                    "live_pull_request_drift",
                    MODULE.merge_clean_dev_pr,
                    client,
                    clean_receipt(),
                    expected_head_sha=HEAD_SHA,
                )
                self.assertEqual(client.push_calls, [])

    def test_human_changes_requested_blocks_merge(self):
        client = FakeClient()
        client.reviews.append(
            {"state": "CHANGES_REQUESTED", "user": {"login": "human-reviewer"}}
        )
        self.assert_code(
            "human_changes_requested",
            MODULE.merge_clean_dev_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )
        self.assertEqual(client.push_calls, [])

    def test_later_human_approval_clears_prior_changes_requested(self):
        client = FakeClient()
        client.reviews.extend(
            [
                {"state": "CHANGES_REQUESTED", "user": {"login": "human-reviewer"}},
                {"state": "APPROVED", "user": {"login": "human-reviewer"}},
            ]
        )
        result = MODULE.merge_clean_dev_pr(client, clean_receipt(), expected_head_sha=HEAD_SHA)
        self.assertEqual(result["status"], "merged")

    def test_expected_head_and_merge_confirmation_are_required(self):
        client = FakeClient()
        self.assert_code(
            "expected_head_mismatch",
            MODULE.merge_clean_dev_pr,
            client,
            clean_receipt(),
            expected_head_sha="4" * 40,
        )
        client.merge_result = {"merged": False, "message": "blocked"}
        self.assert_code(
            "merge_not_confirmed",
            MODULE.merge_clean_dev_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )

    def test_replays_dev_push_automation_suppressed_by_github_token_merge(self):
        client = FakeClient()
        paths = ["scripts/github/cross_repo_workflow_updater.py"]
        client.files = [{"filename": path} for path in paths]
        result = MODULE.merge_clean_dev_pr(
            client, receipt_for_paths(paths), expected_head_sha=HEAD_SHA
        )
        self.assertEqual(result["status"], "merged")
        self.assertEqual(
            result["downstream_dispatches"],
            [MODULE.CROSS_REPO_DISPATCH_WORKFLOW],
        )
        self.assertEqual(len(client.dispatch_calls), 1)
        self.assertEqual(client.dispatch_calls[0][1], "dev")
        self.assertEqual(client.dispatch_calls[0][2]["source_commit"], MERGE_SHA)
        self.assertEqual(client.dispatch_calls[0][2]["previous_source_commit"], BASE_SHA)

    def test_downstream_dispatch_failure_is_durable_after_confirmed_merge(self):
        client = FakeClient()
        paths = ["scripts/github/cross_repo_workflow_updater.py"]
        client.files = [{"filename": path} for path in paths]
        client.dispatch_failure = True
        result = MODULE.merge_clean_dev_pr(
            client, receipt_for_paths(paths), expected_head_sha=HEAD_SHA
        )
        self.assertEqual(result["status"], "merged_with_downstream_failure")
        self.assertEqual(result["merge_commit_sha"], MERGE_SHA)
        self.assertEqual(
            result["downstream_dispatch_failures"],
            [MODULE.CROSS_REPO_DISPATCH_WORKFLOW],
        )

    def test_newer_same_head_failed_or_pending_check_supersedes_clean_receipt(self):
        for status in ("failure", "pending"):
            with self.subTest(status=status):
                client = FakeClient()
                client.check_runs.append(
                    check_run(204, "speculoos", "github-actions", status=status, suite_id=902)
                )
                self.assert_code(
                    "fresh_required_evidence_not_successful",
                    MODULE.merge_clean_dev_pr,
                    client,
                    clean_receipt(),
                    expected_head_sha=HEAD_SHA,
                )
                self.assertEqual(client.push_calls, [])

    def test_retarget_after_final_get_cannot_redirect_server_mutation(self):
        client = FakeClient()
        stable_before = client.refs["main"]

        def retarget_after_final_get(value):
            value.pr["base"] = {"ref": "main", "sha": stable_before}

        client.before_push = retarget_after_final_get
        result = MODULE.merge_clean_dev_pr(
            client, clean_receipt(), expected_head_sha=HEAD_SHA
        )
        self.assertEqual(result["status"], "merged")
        self.assertEqual(client.refs["dev"], MERGE_SHA)
        self.assertEqual(client.refs["main"], stable_before)
        self.assertEqual(client.push_calls[0][0]["base_ref"], "dev")

    def test_base_advance_during_push_fails_exact_base_compare_and_swap(self):
        client = FakeClient()
        advanced = "4" * 40

        def advance_base(value):
            value.refs["dev"] = advanced

        client.before_push = advance_base
        self.assert_code(
            "base_compare_and_swap_failed",
            MODULE.merge_clean_dev_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )
        self.assertEqual(client.refs["dev"], advanced)

    def test_real_normal_push_builds_two_parent_merge_on_exact_base(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            remote = root / "remote.git"
            subprocess.run(["git", "init", "-b", "dev", str(source)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
            (source / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "base.txt"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-m", "base"], check=True, stdout=subprocess.DEVNULL)
            base_sha = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
            ).strip()
            subprocess.run(["git", "-C", str(source), "switch", "-c", "feat/test"], check=True, stdout=subprocess.DEVNULL)
            (source / "head.txt").write_text("head\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "head.txt"], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-m", "head"], check=True, stdout=subprocess.DEVNULL)
            head_sha = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
            ).strip()
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(source), "remote", "add", "origin", str(remote)], check=True)
            subprocess.run(
                ["git", "-C", str(source), "push", "origin", "dev:refs/heads/dev", f"{head_sha}:refs/pull/95/head"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            class LocalClient(MODULE.GitHubMergeClient):
                def _repository_remote(self):
                    return str(remote)

            client = LocalClient("https://api.github.com", "test-token", "fr-meyer/agent-toolkit")
            result = client.push_exact_merge(
                {
                    "repository_slug": "fr-meyer/agent-toolkit",
                    "pr_number": 95,
                    "base_ref": "dev",
                    "base_sha": base_sha,
                    "head_ref": "feat/test",
                    "head_sha": head_sha,
                    "head_repository_slug": "fr-meyer/agent-toolkit",
                },
                "Test merge",
            )
            remote_tip = subprocess.check_output(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/dev"], text=True
            ).strip()
            commit = subprocess.check_output(
                ["git", "--git-dir", str(remote), "cat-file", "-p", remote_tip], text=True
            )
            self.assertEqual(result["sha"], remote_tip)
            self.assertIn(f"parent {base_sha}\n", commit)
            self.assertIn(f"parent {head_sha}\n", commit)


if __name__ == "__main__":
    unittest.main()
