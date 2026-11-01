import copy
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_review_contract.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_review_contract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

REPOSITORY = "fr-meyer/agent-toolkit"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
POLICY = MODULE.trusted_author_policy.load_policy(REPOSITORY)
POLICY_DIGEST = MODULE.trusted_author_policy.policy_digest(POLICY)
MARKER_BODY = (
    "> ✅ No new issues found.\n"
    "<!-- PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ -->\n"
    "<sup>Using `gpt-6.1-sol`</sup>"
)


def identity():
    return {
        "repository_slug": REPOSITORY,
        "pr_number": 95,
        "base_ref": "dev",
        "base_sha": BASE_SHA,
        "head_ref": "feat/pullfrog-write-capable-loop",
        "head_sha": HEAD_SHA,
        "head_repository_slug": REPOSITORY,
        "base_repository_slug": REPOSITORY,
        "author_login": "fr-meyer",
        "author_account_id": 26621962,
        "author_type": "User",
        "trusted_author_policy_schema": POLICY["schema"],
        "trusted_author_policy_digest": POLICY_DIGEST,
    }


def check(name, conclusion="success", check_id=100, app="pullfrog", suite_id=50):
    return {
        "id": check_id,
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "head_sha": HEAD_SHA,
        "app": {"slug": app},
        "check_suite": {"id": suite_id},
    }


def review(body=MARKER_BODY, review_id=601):
    return {
        "id": review_id,
        "commit_id": HEAD_SHA,
        "submitted_at": "2026-10-29T00:00:00Z",
        "state": "COMMENTED",
        "body": body,
        "user": {"login": "pullfrog[bot]"},
    }


def thread(*, resolved=True, author="pullfrog[bot]", review_id=601):
    return {
        "id": "PRRT_contract_fixture",
        "isResolved": resolved,
        "isOutdated": False,
        "path": "scripts/example.py",
        "line": 12,
        "comments": {
            "nodes": [
                {
                    "databaseId": 701,
                    "author": {"login": author},
                    "pullRequestReview": {"databaseId": review_id},
                }
            ]
        },
    }


def snapshot():
    return {
        "schema": MODULE.SNAPSHOT_SCHEMA,
        "expected_identity": identity(),
        "observed_identity": identity(),
        "reviews": [review()],
        "review_comments": [],
        "review_threads": [thread()],
        "check_runs": [
            check("pullfrog", check_id=100),
            check("pullfrog-approval", check_id=101),
        ],
    }


class PullfrogReviewContractTests(unittest.TestCase):
    def test_clean_contract_requires_complete_exact_identity(self):
        receipt = MODULE.evaluate_contract(snapshot())
        self.assertEqual(receipt["status"], "clean")
        self.assertEqual(receipt["blockers"], [])
        self.assertEqual(receipt["review"]["finding_count"], 0)
        self.assertEqual(receipt["threads"]["unresolved_pullfrog_count"], 0)
        self.assertEqual(receipt["checks"]["pullfrog"]["check_run_id"], 100)
        self.assertEqual(
            receipt["gate"]["external_id"],
            MODULE.gate_external_id(
                identity(),
                MODULE.NATIVE_EVIDENCE_PROFILE,
                receipt["evidence_digest"],
            ),
        )

    def test_fork_review_evidence_is_valid_but_gate_publication_is_not(self):
        fixture = snapshot()
        for key in ("expected_identity", "observed_identity"):
            fixture[key]["head_repository_slug"] = "external/agent-toolkit"
        receipt = MODULE.evaluate_contract(fixture)
        self.assertEqual(receipt["status"], "clean")
        self.assertEqual(receipt["blockers"], [])
        self.assertEqual(receipt["gate"]["external_id"], "")
        selected = MODULE.select_gate([], fixture["observed_identity"], [receipt])
        self.assertEqual(selected["status"], "missing")
        self.assertEqual(selected["expected_external_ids"], [])

    def test_review_identity_requires_governed_dev_or_main_base(self):
        for base_ref in ("staging", "master"):
            with self.subTest(base_ref=base_ref):
                fixture = snapshot()
                for key in ("expected_identity", "observed_identity"):
                    fixture[key]["base_ref"] = base_ref
                receipt = MODULE.evaluate_contract(fixture)
                self.assertEqual(receipt["status"], "incomplete")
                self.assertIn(
                    "invalid_expected_review_identity", receipt["blockers"]
                )

    def test_empty_or_markerless_review_is_never_complete(self):
        for body in ("", "No new issues found"):
            with self.subTest(body=body):
                fixture = snapshot()
                fixture["reviews"] = [review(body=body)]
                receipt = MODULE.evaluate_contract(fixture)
                self.assertEqual(receipt["status"], "incomplete")
                self.assertIn("missing_complete_primary_verdict", receipt["blockers"])

    def test_findings_authorize_remediation_but_not_clean_gate(self):
        fixture = snapshot()
        fixture["check_runs"][1] = check(
            "pullfrog-approval", conclusion="failure", check_id=101
        )
        fixture["reviews"] = [review(body=MARKER_BODY.replace("No new issues found", "One issue"))]
        fixture["review_comments"] = [
            {
                "id": 701,
                "pull_request_review_id": 601,
                "commit_id": HEAD_SHA,
                "path": "scripts/example.py",
                "line": 12,
                "body": "Fix the exact-head comparison.",
                "user": {"login": "pullfrog[bot]"},
            }
        ]
        fixture["review_threads"] = [thread(resolved=False)]
        receipt = MODULE.evaluate_contract(fixture)
        self.assertEqual(receipt["status"], "findings")
        self.assertEqual(receipt["blockers"], [])
        self.assertEqual(receipt["review"]["finding_count"], 1)
        self.assertEqual(receipt["gate"]["conclusion"], "failure")

    def test_unresolved_pullfrog_thread_blocks_clean_verdict(self):
        fixture = snapshot()
        fixture["review_threads"] = [thread(resolved=False)]
        receipt = MODULE.evaluate_contract(fixture)
        self.assertEqual(receipt["status"], "reconciliation_required")
        self.assertIn("unresolved_pullfrog_review_threads", receipt["blockers"])

    def test_review_only_profile_allows_clean_reconciliation_before_approval(self):
        fixture = snapshot()
        fixture["check_runs"] = [
            check("pullfrog-approval", conclusion="failure", check_id=101)
        ]
        fixture["review_threads"] = [thread(resolved=False, review_id=500)]
        receipt = MODULE.evaluate_contract(
            fixture,
            MODULE.REVIEW_ONLY_EVIDENCE_PROFILE,
        )
        self.assertEqual(receipt["status"], "reconciliation_required")
        self.assertEqual(receipt["review"]["finding_count"], 0)
        self.assertEqual(receipt["evidence_profile"], "review-only")

        fixture["review_threads"] = [thread(resolved=True, review_id=500)]
        clean = MODULE.evaluate_contract(
            fixture,
            MODULE.REVIEW_ONLY_EVIDENCE_PROFILE,
        )
        self.assertEqual(clean["status"], "clean")
        self.assertEqual(clean["blockers"], [])

    def test_review_only_profile_keeps_genuine_findings(self):
        fixture = snapshot()
        fixture["check_runs"] = []
        fixture["reviews"] = [
            review(body=MARKER_BODY.replace("No new issues found", "One issue"))
        ]
        fixture["review_comments"] = [
            {
                "id": 701,
                "pull_request_review_id": 601,
                "commit_id": HEAD_SHA,
                "path": "scripts/example.py",
                "line": 12,
                "body": "Fix the exact-head comparison.",
                "user": {"login": "pullfrog[bot]"},
            }
        ]
        receipt = MODULE.evaluate_contract(
            fixture,
            MODULE.REVIEW_ONLY_EVIDENCE_PROFILE,
        )
        self.assertEqual(receipt["status"], "findings")
        self.assertEqual(receipt["review"]["finding_count"], 1)

    def test_review_only_profile_requires_the_exact_clean_verdict_line(self):
        fixture = snapshot()
        fixture["check_runs"] = []
        fixture["reviews"] = [
            review(
                body=(
                    "> One issue remains; the phrase no new issues found is not a verdict.\n"
                    "<!-- PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ -->"
                )
            )
        ]
        receipt = MODULE.evaluate_contract(
            fixture,
            MODULE.REVIEW_ONLY_EVIDENCE_PROFILE,
        )
        self.assertEqual(receipt["status"], "findings")
        self.assertEqual(receipt["review"]["finding_count"], 1)

    def test_non_pullfrog_thread_does_not_block(self):
        fixture = snapshot()
        fixture["review_threads"] = [thread(resolved=False, author="human-reviewer")]
        self.assertEqual(MODULE.evaluate_contract(fixture)["status"], "clean")

    def test_missing_complete_identity_fields_fail_closed(self):
        for field in (
            "base_repository_slug",
            "author_login",
            "author_account_id",
            "author_type",
            "trusted_author_policy_schema",
            "trusted_author_policy_digest",
        ):
            with self.subTest(field=field):
                fixture = snapshot()
                fixture["expected_identity"].pop(field)
                fixture["observed_identity"].pop(field)
                receipt = MODULE.evaluate_contract(fixture)
                self.assertEqual(receipt["status"], "incomplete")
                self.assertIn("invalid_expected_review_identity", receipt["blockers"])
                self.assertIn("invalid_observed_review_identity", receipt["blockers"])

    def test_identity_actor_check_app_suite_and_head_drift_fail_closed(self):
        mutations = []
        changed = snapshot()
        changed["observed_identity"]["base_sha"] = "3" * 40
        mutations.append((changed, "review_identity_drift"))
        changed = snapshot()
        changed["observed_identity"]["author_login"] = "other-user"
        mutations.append((changed, "review_identity_drift"))
        changed = snapshot()
        changed["observed_identity"]["author_account_id"] = 285669409
        mutations.append((changed, "review_identity_drift"))
        changed = snapshot()
        changed["observed_identity"]["trusted_author_policy_digest"] = "9" * 64
        mutations.append((changed, "review_identity_drift"))
        changed = snapshot()
        changed["reviews"][0]["user"]["login"] = "attacker"
        mutations.append((changed, "missing_complete_primary_verdict"))
        changed = snapshot()
        changed["check_runs"][0]["app"]["slug"] = "attacker"
        mutations.append((changed, "pullfrog_check_spoofed"))
        changed = snapshot()
        changed["check_runs"][1]["check_suite"]["id"] = 51
        mutations.append((changed, "pullfrog_check_suite_mismatch"))
        changed = snapshot()
        changed["check_runs"][0]["head_sha"] = "3" * 40
        mutations.append((changed, "pullfrog_check_stale"))
        for fixture, blocker in mutations:
            with self.subTest(blocker=blocker):
                receipt = MODULE.evaluate_contract(fixture)
                self.assertEqual(receipt["status"], "incomplete")
                self.assertIn(blocker, receipt["blockers"])

    def test_gate_selector_binds_repository_pr_base_and_head(self):
        expected = identity()
        contract = MODULE.evaluate_contract(snapshot())
        external_id = MODULE.gate_external_id(
            expected,
            contract["evidence_profile"],
            contract["evidence_digest"],
        )
        runs = [
            {
                "id": 900,
                "name": MODULE.GATE_NAME,
                "status": "completed",
                "conclusion": "success",
                "head_sha": HEAD_SHA,
                "external_id": external_id,
                "app": {"slug": MODULE.GATE_APP},
                "check_suite": {"id": 80},
            }
        ]
        selected = MODULE.select_gate(runs, expected, [contract])
        self.assertEqual(selected["status"], "success")
        self.assertEqual(selected["evidence_profile"], "native")
        drift = copy.deepcopy(expected)
        drift["base_sha"] = "3" * 40
        selected = MODULE.select_gate(runs, drift, [contract])
        self.assertEqual(selected["status"], "missing")
        self.assertTrue(selected["external_id_mismatch"])
        for field, value in (
            ("author_account_id", 285669409),
            ("author_login", "other-user"),
            ("trusted_author_policy_digest", "9" * 64),
        ):
            with self.subTest(field=field):
                drift = copy.deepcopy(expected)
                drift[field] = value
                selected = MODULE.select_gate(runs, drift, [contract])
                self.assertEqual(selected["status"], "missing")
                self.assertTrue(selected["external_id_mismatch"])

    def test_gate_is_invalidated_by_newer_same_head_check_evidence(self):
        contract = MODULE.evaluate_contract(snapshot())
        external_id = contract["gate"]["external_id"]
        runs = [
            {
                "id": 900,
                "name": MODULE.GATE_NAME,
                "status": "completed",
                "conclusion": "success",
                "head_sha": HEAD_SHA,
                "external_id": external_id,
                "app": {"slug": MODULE.GATE_APP},
                "check_suite": {"id": 80},
            }
        ]
        changed = snapshot()
        changed["check_runs"][1] = check(
            "pullfrog-approval", conclusion="failure", check_id=202
        )
        changed_contract = MODULE.evaluate_contract(changed)
        selected = MODULE.select_gate(runs, identity(), [changed_contract])
        self.assertEqual(selected["status"], "missing")
        self.assertTrue(selected["external_id_mismatch"])

    def test_gate_selector_binds_failed_gate_to_current_findings_contract(self):
        changed = snapshot()
        changed["check_runs"][1] = check(
            "pullfrog-approval", conclusion="failure", check_id=202
        )
        changed["review_comments"] = [
            {
                "id": 701,
                "pull_request_review_id": 601,
                "commit_id": HEAD_SHA,
                "path": "scripts/example.py",
                "line": 12,
                "body": "A current exact-head finding.",
                "user": {"login": "pullfrog[bot]"},
            }
        ]
        contract = MODULE.evaluate_contract(changed)
        self.assertEqual(contract["status"], "findings")
        runs = [
            {
                "id": 900,
                "name": MODULE.GATE_NAME,
                "status": "completed",
                "conclusion": "failure",
                "head_sha": HEAD_SHA,
                "external_id": contract["gate"]["external_id"],
                "app": {"slug": MODULE.GATE_APP},
                "check_suite": {"id": 80},
            }
        ]
        selected = MODULE.select_gate(runs, identity(), [contract])
        self.assertEqual(selected["status"], "failure")
        self.assertEqual(selected["contract_status"], "findings")
        self.assertEqual(selected["evidence_digest"], contract["evidence_digest"])

    def test_thread_collection_fails_closed_on_missing_connection(self):
        class Client:
            def graphql(self, query, variables):
                return {"data": {"repository": {"pullRequest": None}}}

        with self.assertRaises(MODULE.ReviewContractError) as raised:
            MODULE.collect_review_threads(Client(), identity())
        self.assertEqual(raised.exception.code, "invalid_review_thread_response")


if __name__ == "__main__":
    unittest.main()
