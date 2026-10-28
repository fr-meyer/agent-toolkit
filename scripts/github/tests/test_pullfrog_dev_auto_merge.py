import copy
import importlib.util
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
            "event_head_sha": repository["head_sha"],
        },
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
        self.reviews = []
        self.files = [{"filename": "scripts/example.py"}]
        self.merge_result = {"merged": True, "sha": MERGE_SHA}
        self.merge_calls = []
        self.dispatch_calls = []
        self.dispatch_failure = False

    def get(self, path):
        if path == f"{self.allowed_prefix}/pulls/95":
            return copy.deepcopy(self.pr)
        raise AssertionError(path)

    def paginated(self, path):
        if path == f"{self.allowed_prefix}/pulls/95/reviews":
            return copy.deepcopy(self.reviews)
        if path == f"{self.allowed_prefix}/pulls/95/files":
            return copy.deepcopy(self.files)
        raise AssertionError(path)

    def merge_exact_head(self, identity, title):
        self.merge_calls.append((copy.deepcopy(identity), title))
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
        self.assertFalse(result["branch_deleted"])
        self.assertEqual(len(client.merge_calls), 1)
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
                self.assertEqual(client.merge_calls, [])

    def test_human_changes_requested_blocks_merge(self):
        client = FakeClient()
        client.reviews = [
            {"state": "CHANGES_REQUESTED", "user": {"login": "human-reviewer"}},
            {"state": "COMMENTED", "user": {"login": "pullfrog[bot]"}},
        ]
        self.assert_code(
            "human_changes_requested",
            MODULE.merge_clean_dev_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )
        self.assertEqual(client.merge_calls, [])

    def test_later_human_approval_clears_prior_changes_requested(self):
        client = FakeClient()
        client.reviews = [
            {"state": "CHANGES_REQUESTED", "user": {"login": "human-reviewer"}},
            {"state": "APPROVED", "user": {"login": "human-reviewer"}},
        ]
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
        client.files = [
            {"filename": "templates/starter-workflows/pullfrog.yml"},
            {"filename": "templates/workflow-ref-sync-manifest.json"},
        ]
        result = MODULE.merge_clean_dev_pr(
            client, clean_receipt(), expected_head_sha=HEAD_SHA
        )
        self.assertEqual(result["status"], "merged")
        self.assertEqual(
            result["downstream_dispatches"],
            [
                MODULE.CROSS_REPO_DISPATCH_WORKFLOW,
                MODULE.REF_SYNC_DISPATCH_WORKFLOW,
            ],
        )
        self.assertEqual(len(client.dispatch_calls), 2)
        self.assertEqual(client.dispatch_calls[0][1], "dev")
        self.assertEqual(client.dispatch_calls[0][2]["source_commit"], MERGE_SHA)
        self.assertEqual(client.dispatch_calls[0][2]["previous_source_commit"], BASE_SHA)
        self.assertEqual(client.dispatch_calls[1][2]["after_sha"], MERGE_SHA)

    def test_downstream_dispatch_failure_is_durable_after_confirmed_merge(self):
        client = FakeClient()
        client.files = [{"filename": "templates/starter-workflows/pullfrog.yml"}]
        client.dispatch_failure = True
        result = MODULE.merge_clean_dev_pr(
            client, clean_receipt(), expected_head_sha=HEAD_SHA
        )
        self.assertEqual(result["status"], "merged_with_downstream_failure")
        self.assertEqual(result["merge_commit_sha"], MERGE_SHA)
        self.assertEqual(
            result["downstream_dispatch_failures"],
            [MODULE.CROSS_REPO_DISPATCH_WORKFLOW],
        )


if __name__ == "__main__":
    unittest.main()
