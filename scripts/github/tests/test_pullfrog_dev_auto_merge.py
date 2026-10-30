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

COORDINATOR_TEST_SCRIPT = Path(__file__).with_name("test_pullfrog_cloud_coordinator.py")
COORDINATOR_TEST_SPEC = importlib.util.spec_from_file_location(
    "pullfrog_cloud_coordinator_producer_test", COORDINATOR_TEST_SCRIPT
)
COORDINATOR_TEST = importlib.util.module_from_spec(COORDINATOR_TEST_SPEC)
assert COORDINATOR_TEST_SPEC.loader is not None
COORDINATOR_TEST_SPEC.loader.exec_module(COORDINATOR_TEST)

BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
MERGE_SHA = "3" * 40


def check_run(
    check_id,
    name,
    app_slug,
    *,
    status="success",
    suite_id=900,
    external_id="",
):
    item = {
        "id": check_id,
        "name": name,
        "head_sha": HEAD_SHA,
        "status": "completed" if status != "pending" else "in_progress",
        "conclusion": status if status != "pending" else None,
        "app": {"slug": app_slug},
        "check_suite": {"id": suite_id},
    }
    if external_id:
        item["external_id"] = external_id
    return item


def review_identity(base_ref="dev"):
    return {
        "repository_slug": "fr-meyer/agent-toolkit",
        "pr_number": 95,
        "base_ref": base_ref,
        "base_sha": BASE_SHA,
        "base_repository_slug": "fr-meyer/agent-toolkit",
        "head_ref": "feat/pullfrog-write-capable-loop",
        "head_sha": HEAD_SHA,
        "head_repository_slug": "fr-meyer/agent-toolkit",
    }


def exact_head_reviews():
    return [
        {
            "id": 700,
            "state": "COMMENTED",
            "body": (
                "No new issues found.\n"
                "<!-- PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ -->"
            ),
            "commit_id": HEAD_SHA,
            "submitted_at": "2026-10-28T00:00:00Z",
            "user": {"login": "pullfrog[bot]"},
        }
    ]


def raw_pullfrog_checks():
    return [
        check_run(101, "pullfrog", "pullfrog", suite_id=900),
        check_run(102, "pullfrog-approval", "pullfrog", suite_id=900),
    ]


def clean_review_contract(base_ref="dev"):
    identity = review_identity(base_ref)
    return MODULE.review_contract.evaluate_contract(
        {
            "schema": MODULE.review_contract.SNAPSHOT_SCHEMA,
            "expected_identity": identity,
            "observed_identity": identity,
            "reviews": exact_head_reviews(),
            "review_comments": [],
            "review_threads": [],
            "check_runs": raw_pullfrog_checks(),
        }
    )


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
    contract = clean_review_contract()
    check_details = {
        "pullfrog": {
            "name": "pullfrog",
            "app_slug": "pullfrog",
            "status": "success",
            "head_sha": HEAD_SHA,
            "check_run_id": 101,
            "check_suite_id": 900,
        },
        "pullfrog_approval": {
            "name": "pullfrog-approval",
            "app_slug": "pullfrog",
            "status": "success",
            "head_sha": HEAD_SHA,
            "check_run_id": 102,
            "check_suite_id": 900,
        },
        "pullfrog_review_gate": {
            "name": MODULE.review_contract.GATE_NAME,
            "app_slug": MODULE.review_contract.GATE_APP,
            "status": "success",
            "head_sha": HEAD_SHA,
            "check_run_id": 105,
            "check_suite_id": 903,
            "external_id": contract["gate"]["external_id"],
            "evidence_profile": contract["evidence_profile"],
            "evidence_digest": contract["evidence_digest"],
        },
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
        "review_contract": contract,
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


def review_only_receipt():
    receipt = clean_receipt()
    identity = review_identity()
    contract = MODULE.review_contract.evaluate_contract(
        {
            "schema": MODULE.review_contract.SNAPSHOT_SCHEMA,
            "expected_identity": identity,
            "observed_identity": identity,
            "reviews": exact_head_reviews(),
            "review_comments": [],
            "review_threads": [],
            "check_runs": [],
        },
        MODULE.review_contract.REVIEW_ONLY_EVIDENCE_PROFILE,
    )
    receipt["review_contract"] = contract
    gate = receipt["checks"]["pullfrog_review_gate"]
    gate["external_id"] = contract["gate"]["external_id"]
    gate["evidence_profile"] = contract["evidence_profile"]
    gate["evidence_digest"] = contract["evidence_digest"]
    return receipt


def retarget_base(receipt, client, base_ref):
    receipt["identity"]["base_ref"] = base_ref
    receipt["cycle_decision"]["repository"]["base_ref"] = base_ref
    client.pr["base"]["ref"] = base_ref
    client.refs[base_ref] = BASE_SHA
    client.merge_result["base_ref"] = base_ref
    contract = clean_review_contract(base_ref)
    receipt["review_contract"] = contract
    receipt_gate = receipt["checks"]["pullfrog_review_gate"]
    receipt_gate["external_id"] = contract["gate"]["external_id"]
    receipt_gate["evidence_profile"] = contract["evidence_profile"]
    receipt_gate["evidence_digest"] = contract["evidence_digest"]
    live_gate = next(
        item
        for item in client.check_runs
        if item["name"] == MODULE.review_contract.GATE_NAME
    )
    live_gate["external_id"] = contract["gate"]["external_id"]
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
        self.reviews = exact_head_reviews()
        self.comments = []
        self.review_threads = []
        self.files = [{"filename": "scripts/example.py"}]
        contract = clean_review_contract()
        self.check_runs = raw_pullfrog_checks() + [
            check_run(
                105,
                MODULE.review_contract.GATE_NAME,
                MODULE.review_contract.GATE_APP,
                suite_id=903,
                external_id=contract["gate"]["external_id"],
            ),
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
            "transport": "exact-old-oid-normal-fast-forward-push",
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

    def graphql(self, query, variables):
        return {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": copy.deepcopy(self.review_threads),
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        }

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

    def test_unmodified_coordinator_receipt_passes_validation_and_fresh_evidence(self):
        snapshot = COORDINATOR_TEST.base_snapshot()
        identity = COORDINATOR_TEST.MODULE._identity_from_pr(
            snapshot["repository_slug"],
            snapshot["observed_pull_request"],
            snapshot["repository"]["default_branch"],
            snapshot["policy"]["protected_refs"],
        )
        contract = MODULE.review_contract.evaluate_contract(
            {
                "schema": MODULE.review_contract.SNAPSHOT_SCHEMA,
                "expected_identity": identity,
                "observed_identity": identity,
                "reviews": snapshot["reviews"],
                "review_comments": snapshot["review_comments"],
                "review_threads": snapshot["review_threads"],
                "check_runs": snapshot["check_runs"],
            }
        )
        snapshot["check_runs"].append(
            COORDINATOR_TEST.check(
                MODULE.review_contract.GATE_NAME,
                app=MODULE.review_contract.GATE_APP,
                check_id=999,
                suite_id=903,
            )
        )
        snapshot["check_runs"][-1]["external_id"] = contract["gate"]["external_id"]
        receipt = COORDINATOR_TEST.MODULE.evaluate_snapshot(snapshot)
        identity = MODULE.validate_clean_receipt(receipt)

        class ProducerClient:
            allowed_prefix = "/repos/fr-meyer/agent-toolkit"

            def get(self, path):
                expected = (
                    f"{self.allowed_prefix}/commits/{identity['head_sha']}"
                    "/check-runs?per_page=100"
                )
                if path != expected:
                    raise AssertionError(path)
                return {
                    "total_count": len(snapshot["check_runs"]),
                    "check_runs": copy.deepcopy(snapshot["check_runs"]),
                }

            def paginated(self, path):
                expected = f"{self.allowed_prefix}/pulls/{identity['pr_number']}/comments"
                if path != expected:
                    raise AssertionError(path)
                return copy.deepcopy(snapshot["review_comments"])

            def graphql(self, query, variables):
                return {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "reviewThreads": {
                                    "nodes": copy.deepcopy(snapshot["review_threads"]),
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                }
                            }
                        }
                    }
                }

        changed_paths = sorted(item["filename"] for item in snapshot["files"])
        fresh = MODULE._refresh_exact_head_evidence(
            ProducerClient(),
            receipt,
            identity,
            repository=snapshot["repository"],
            changed_paths=changed_paths,
            reviews=snapshot["reviews"],
        )
        self.assertEqual(fresh["pullfrog_review_gate_id"], 999)
        self.assertEqual(fresh["check_run_ids"]["ci"], [102])

    def test_clean_exact_head_dev_pr_merges_once(self):
        client = FakeClient()
        result = MODULE.merge_clean_pr(client, clean_receipt(), expected_head_sha=HEAD_SHA)
        self.assertEqual(result["status"], "merged")
        self.assertEqual(result["base_ref"], "dev")
        self.assertEqual(result["head_sha"], HEAD_SHA)
        self.assertEqual(result["merge_commit_sha"], MERGE_SHA)
        self.assertEqual(result["merge_method"], "merge")
        self.assertEqual(
            result["merge_transport"], "exact-old-oid-normal-fast-forward-push"
        )
        self.assertFalse(result["branch_deleted"])
        self.assertEqual(len(client.push_calls), 1)
        self.assertEqual(result["downstream_dispatches"], [])
        self.assertEqual(result["downstream_dispatch_failures"], [])

    def test_clean_review_only_gate_merges_without_raw_pullfrog_checks(self):
        client = FakeClient()
        client.check_runs = [
            item
            for item in client.check_runs
            if item["name"] not in {"pullfrog", "pullfrog-approval"}
        ]
        receipt = review_only_receipt()
        gate = next(
            item
            for item in client.check_runs
            if item["name"] == MODULE.review_contract.GATE_NAME
        )
        gate["external_id"] = receipt["review_contract"]["gate"]["external_id"]
        result = MODULE.merge_clean_pr(client, receipt, expected_head_sha=HEAD_SHA)
        self.assertEqual(result["status"], "merged")
        self.assertEqual(
            receipt["review_contract"]["evidence_profile"],
            MODULE.review_contract.REVIEW_ONLY_EVIDENCE_PROFILE,
        )
        self.assertEqual(len(client.push_calls), 1)

    def test_clean_exact_head_non_stable_base_is_eligible(self):
        client = FakeClient()
        receipt = retarget_base(clean_receipt(), client, "staging")
        result = MODULE.merge_clean_pr(client, receipt, expected_head_sha=HEAD_SHA)
        self.assertEqual(result["status"], "merged")
        self.assertEqual(result["base_ref"], "staging")
        self.assertEqual(client.refs["staging"], MERGE_SHA)
        self.assertEqual(client.refs["dev"], BASE_SHA)

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

    def test_receipt_requires_clean_exact_identity_review_contract(self):
        variants = (
            ("status", "findings"),
            ("review_id", 701),
            ("unresolved_threads", 1),
            ("base_sha", "4" * 40),
            ("evidence_digest", "4" * 64),
        )
        for field, value in variants:
            with self.subTest(field=field):
                receipt = clean_receipt()
                if field == "status":
                    receipt["review_contract"]["status"] = value
                elif field == "review_id":
                    receipt["review_contract"]["review"]["review_id"] = value
                elif field == "unresolved_threads":
                    receipt["review_contract"]["threads"][
                        "unresolved_pullfrog_count"
                    ] = value
                elif field == "evidence_digest":
                    receipt["review_contract"][field] = value
                else:
                    receipt["review_contract"]["identity"][field] = value
                self.assert_code(
                    "invalid_review_contract", MODULE.validate_clean_receipt, receipt
                )

    def test_receipt_gate_must_match_contract_profile_and_digest(self):
        for field, value in (
            ("external_id", "pullfrog-review-gate:v3:invalid"),
            ("evidence_profile", MODULE.review_contract.REVIEW_ONLY_EVIDENCE_PROFILE),
            ("evidence_digest", "5" * 64),
            ("status", "failure"),
        ):
            with self.subTest(field=field):
                receipt = clean_receipt()
                receipt["checks"]["pullfrog_review_gate"][field] = value
                self.assert_code(
                    "invalid_receipt_check_details",
                    MODULE.validate_clean_receipt,
                    receipt,
                )

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
                    MODULE.merge_clean_pr,
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
            MODULE.merge_clean_pr,
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
        result = MODULE.merge_clean_pr(client, clean_receipt(), expected_head_sha=HEAD_SHA)
        self.assertEqual(result["status"], "merged")

    def test_expected_head_and_merge_confirmation_are_required(self):
        client = FakeClient()
        self.assert_code(
            "expected_head_mismatch",
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha="4" * 40,
        )
        client.merge_result = {"merged": False, "message": "blocked"}
        self.assert_code(
            "merge_not_confirmed",
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )

    def test_replays_dev_push_automation_suppressed_by_github_token_merge(self):
        client = FakeClient()
        paths = ["scripts/github/cross_repo_workflow_updater.py"]
        client.files = [{"filename": path} for path in paths]
        result = MODULE.merge_clean_pr(
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

    def test_non_dev_merge_does_not_replay_dev_push_automation(self):
        client = FakeClient()
        paths = ["scripts/github/cross_repo_workflow_updater.py"]
        client.files = [{"filename": path} for path in paths]
        receipt = retarget_base(receipt_for_paths(paths), client, "staging")
        result = MODULE.merge_clean_pr(client, receipt, expected_head_sha=HEAD_SHA)
        self.assertEqual(result["status"], "merged")
        self.assertEqual(result["downstream_dispatches"], [])
        self.assertEqual(client.dispatch_calls, [])

    def test_downstream_dispatch_failure_is_durable_after_confirmed_merge(self):
        client = FakeClient()
        paths = ["scripts/github/cross_repo_workflow_updater.py"]
        client.files = [{"filename": path} for path in paths]
        client.dispatch_failure = True
        result = MODULE.merge_clean_pr(
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
                    MODULE.merge_clean_pr,
                    client,
                    clean_receipt(),
                    expected_head_sha=HEAD_SHA,
                )
                self.assertEqual(client.push_calls, [])

    def test_newer_same_head_review_finding_invalidates_earlier_clean_gate(self):
        client = FakeClient()
        client.comments.append(
            {
                "id": 801,
                "pull_request_review_id": 700,
                "commit_id": HEAD_SHA,
                "path": "scripts/example.py",
                "line": 12,
                "body": "A newer exact-head finding.",
                "user": {"login": "pullfrog[bot]"},
            }
        )
        self.assert_code(
            "fresh_pullfrog_review_gate_ambiguous",
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )
        self.assertEqual(client.push_calls, [])

    def test_success_gate_bound_to_findings_contract_cannot_merge(self):
        client = FakeClient()
        client.comments.append(
            {
                "id": 801,
                "pull_request_review_id": 700,
                "commit_id": HEAD_SHA,
                "path": "scripts/example.py",
                "line": 12,
                "body": "An exact-head finding.",
                "user": {"login": "pullfrog[bot]"},
            }
        )
        identity = review_identity()
        contract = MODULE.review_contract.evaluate_contract(
            {
                "schema": MODULE.review_contract.SNAPSHOT_SCHEMA,
                "expected_identity": identity,
                "observed_identity": identity,
                "reviews": client.reviews,
                "review_comments": client.comments,
                "review_threads": client.review_threads,
                "check_runs": client.check_runs,
            },
            MODULE.review_contract.REVIEW_ONLY_EVIDENCE_PROFILE,
        )
        self.assertEqual(contract["status"], "findings")
        gate = next(
            item
            for item in client.check_runs
            if item["name"] == MODULE.review_contract.GATE_NAME
        )
        gate["external_id"] = contract["gate"]["external_id"]
        self.assert_code(
            "fresh_pullfrog_review_gate_not_successful",
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )
        self.assertEqual(client.push_calls, [])

    def test_newer_failed_or_pending_pullfrog_evidence_invalidates_clean_gate(self):
        for name, status in (
            ("pullfrog", "failure"),
            ("pullfrog-approval", "failure"),
            ("pullfrog-approval", "pending"),
        ):
            with self.subTest(name=name, status=status):
                client = FakeClient()
                client.check_runs.append(
                    check_run(202, name, "pullfrog", status=status, suite_id=900)
                )
                self.assert_code(
                    "fresh_pullfrog_review_gate_ambiguous",
                    MODULE.merge_clean_pr,
                    client,
                    clean_receipt(),
                    expected_head_sha=HEAD_SHA,
                )
                self.assertEqual(client.push_calls, [])

    def test_newer_unresolved_pullfrog_thread_invalidates_clean_gate(self):
        client = FakeClient()
        client.review_threads.append(
            {
                "id": "PRRT_newer_unresolved",
                "isResolved": False,
                "isOutdated": False,
                "path": "scripts/example.py",
                "line": 12,
                "comments": {
                    "nodes": [
                        {
                            "databaseId": 801,
                            "author": {"login": "pullfrog[bot]"},
                            "pullRequestReview": {"databaseId": 700},
                        }
                    ]
                },
            }
        )
        self.assert_code(
            "fresh_pullfrog_review_gate_ambiguous",
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )
        self.assertEqual(client.push_calls, [])

    def test_review_gate_missing_or_failed_fails_closed(self):
        client = FakeClient()
        client.check_runs = [
            item
            for item in client.check_runs
            if item["name"] != MODULE.review_contract.GATE_NAME
        ]
        self.assert_code(
            "fresh_pullfrog_review_gate_not_successful",
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )

        client = FakeClient()
        next(
            item
            for item in client.check_runs
            if item["name"] == MODULE.review_contract.GATE_NAME
        )["conclusion"] = "failure"
        self.assert_code(
            "fresh_pullfrog_review_gate_not_successful",
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )

    def test_review_gate_stale_spoofed_or_identity_unbound_fails_closed(self):
        variants = ("stale", "spoofed", "external_id")
        for variant in variants:
            with self.subTest(variant=variant):
                client = FakeClient()
                gate = next(
                    item
                    for item in client.check_runs
                    if item["name"] == MODULE.review_contract.GATE_NAME
                )
                if variant == "stale":
                    gate["head_sha"] = "4" * 40
                elif variant == "spoofed":
                    gate["app"] = {"slug": "untrusted-app"}
                else:
                    contract = clean_review_contract()
                    gate["external_id"] = MODULE.review_contract.gate_external_id(
                        {
                            **review_identity(),
                            "base_sha": "5" * 40,
                        },
                        contract["evidence_profile"],
                        contract["evidence_digest"],
                    )
                self.assert_code(
                    "fresh_pullfrog_review_gate_ambiguous",
                    MODULE.merge_clean_pr,
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
        result = MODULE.merge_clean_pr(
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
            MODULE.merge_clean_pr,
            client,
            clean_receipt(),
            expected_head_sha=HEAD_SHA,
        )
        self.assertEqual(client.refs["dev"], advanced)

    def test_real_receive_pack_enforces_exact_old_oid_and_builds_two_parent_merge(self):
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
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(remote),
                    "update-ref",
                    "refs/heads/feat/café",
                    base_sha,
                ],
                check=True,
            )

            class LocalClient(MODULE.GitHubMergeClient):
                def _repository_remote(self):
                    return str(remote)

            class RacingClient(LocalClient):
                def _submit_receive_pack(self, remote_path, token, body):
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(source),
                            "push",
                            "origin",
                            f"{head_sha}:refs/heads/dev",
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return super()._submit_receive_pack(remote_path, token, body)

            identity = {
                "repository_slug": "fr-meyer/agent-toolkit",
                "pr_number": 95,
                "base_ref": "dev",
                "base_sha": base_sha,
                "head_ref": "feat/test",
                "head_sha": head_sha,
                "head_repository_slug": "fr-meyer/agent-toolkit",
            }
            racing_client = RacingClient(
                "https://api.github.com", "test-token", "fr-meyer/agent-toolkit"
            )
            self.assert_code(
                "base_compare_and_swap_failed",
                racing_client.push_exact_merge,
                identity,
                "Test stale-base merge",
            )
            raced_tip = subprocess.check_output(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/dev"],
                text=True,
            ).strip()
            self.assertEqual(raced_tip, head_sha)
            subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(remote),
                    "update-ref",
                    "refs/heads/dev",
                    base_sha,
                    head_sha,
                ],
                check=True,
            )

            client = LocalClient("https://api.github.com", "test-token", "fr-meyer/agent-toolkit")
            result = client.push_exact_merge(identity, "Test merge")
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
