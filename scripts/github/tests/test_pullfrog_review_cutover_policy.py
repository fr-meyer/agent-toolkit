import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / ".speculoos/manifest.yaml"
ACTORS = REPO_ROOT / ".speculoos/actors.json"
EVIDENCE = REPO_ROOT / ".speculoos/review-evidence.json"
PUBLISH_POLICY = REPO_ROOT / ".speculoos/publish-policy.yaml"
GOAL = REPO_ROOT / ".speculoos/goal.md"
DOC = REPO_ROOT / "docs/pullfrog-review-only-pilot.md"


class PullfrogReviewCutoverPolicyTests(unittest.TestCase):
    def setUp(self):
        self.manifest = MANIFEST.read_text(encoding="utf-8")
        self.actors = json.loads(ACTORS.read_text(encoding="utf-8"))
        self.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.publish_policy = PUBLISH_POLICY.read_text(encoding="utf-8")
        self.goal = GOAL.read_text(encoding="utf-8")
        self.doc = DOC.read_text(encoding="utf-8")

    def test_manifest_makes_pullfrog_the_only_primary_reviewer(self):
        review_policy = self.manifest.split("review_policy:\n", 1)[1].split(
            "actor_policy:\n", 1
        )[0]
        self.assertIn("  pullfrog_review:\n    policy: primary\n", review_policy)
        self.assertIn("  mergeguez_review:\n    policy: disabled\n", review_policy)
        required = review_policy.split("  required_pr_review:\n", 1)[1]
        self.assertIn("    primary:\n      - pullfrog_review\n", required)
        self.assertNotIn("      - mergeguez_review\n", required)
        self.assertIn("      - pullfrog\n      - pullfrog-approval\n", review_policy)

    def test_actor_policy_separates_review_from_publication_and_merge(self):
        self.assertEqual(self.actors["defaults"]["review_actor"], "pullfrog_review")
        for policy in self.actors["branch_policies"]:
            self.assertEqual(policy["review_actor"], "pullfrog_review")
            self.assertFalse(policy["auto_merge"]["enabled"])
        pullfrog = self.actors["profiles"]["pullfrog_review"]
        self.assertEqual(pullfrog["status"], "active_required_exact_head_reviewer")
        self.assertTrue(pullfrog["required_for_merge"])
        self.assertEqual(
            pullfrog["required_check_names"], ["pullfrog", "pullfrog-approval"]
        )
        self.assertFalse(pullfrog["push_enabled"])
        self.assertEqual(pullfrog["push_mode"], "disabled")
        self.assertFalse(pullfrog["review_remediation_enabled"])
        self.assertEqual(
            pullfrog["review_remediation_mode"],
            "disabled_pending_non_bypassable_push_boundary",
        )
        self.assertFalse(pullfrog["automatic_address_reviews_enabled"])
        self.assertEqual(pullfrog["review_model"], "openai/gpt-sol")
        self.assertEqual(pullfrog["review_effort"], "xhigh")
        self.assertEqual(
            pullfrog["review_remediation_target_model"], "openai/gpt-luna"
        )
        self.assertEqual(pullfrog["review_remediation_target_effort"], "xhigh")
        self.assertEqual(
            pullfrog["remediation_enablement_requires"],
            [
                "non_bypassable_push_destination_guard",
                "first_attempt_and_retry_guard_tests",
                "separate_explicit_authorization",
            ],
        )
        for key in (
            "review_approval_enabled",
            "ci_autofix_enabled",
            "auto_merge_enabled",
        ):
            self.assertFalse(pullfrog[key])
        self.assertEqual(
            self.actors["profiles"]["mergeguez_review"]["status"],
            "disabled_historical",
        )
        self.assertEqual(
            self.actors["branch_policies"][0]["merge_actor"],
            "mergeguez_dev_merge",
        )

    def test_review_evidence_requires_both_exact_head_pullfrog_checks(self):
        requirements = self.evidence["requirements"]
        self.assertIn("pullfrog_review", requirements["required_sources"])
        self.assertNotIn("mergeguez_review", requirements["required_sources"])
        self.assertEqual(requirements["reviewers"]["pullfrog_review"]["policy"], "required")
        self.assertEqual(requirements["reviewers"]["mergeguez_review"]["policy"], "disabled")
        self.assertEqual(
            requirements["reviewer_groups"]["required_pr_review"]["primary"],
            ["pullfrog_review"],
        )
        summary = self.evidence["sources"]["pullfrog_review"]["summary"]
        self.assertIn("pullfrog run check", summary)
        self.assertIn("pullfrog-approval verdict check", summary)

    def test_publish_gate_names_exact_head_pullfrog_checks(self):
        self.assertIn("    - pullfrog_review\n", self.publish_policy)
        self.assertNotIn("    - mergeguez_review\n", self.publish_policy)
        self.assertIn("    - exact_head_pullfrog_status_check\n", self.publish_policy)
        self.assertIn("    - exact_head_pullfrog_approval_check\n", self.publish_policy)
        self.assertNotIn("exact_head_mergeguez_review", self.publish_policy)

    def test_remediation_stays_disabled_until_retry_safe_guard_exists(self):
        self.assertIn(
            "    mode: disabled_pending_non_bypassable_push_boundary\n",
            self.publish_policy,
        )
        self.assertIn(
            "      - non_bypassable_push_destination_guard\n",
            self.publish_policy,
        )
        self.assertIn(
            "      - forbidden_destination_rejected_on_first_attempt\n",
            self.publish_policy,
        )
        self.assertIn(
            "      - forbidden_destination_rejected_after_hook_failure_retry\n",
            self.publish_policy,
        )
        self.assertIn(
            "      - approved_feature_branch_destination_allowed\n",
            self.publish_policy,
        )
        self.assertIn(
            "      - separate_explicit_human_authorization\n",
            self.publish_policy,
        )

    def test_documentation_preserves_human_merge_and_fail_closed_controls(self):
        combined = self.goal + "\n" + self.doc
        self.assertIn("Pullfrog as the primary required reviewer", combined)
        self.assertIn("explicit human merge authority", combined)
        self.assertIn("Mergeguez review is historical only", combined)
        self.assertIn("push: disabled", combined)
        self.assertIn("openai/gpt-sol", combined)
        self.assertIn("openai/gpt-luna", combined)
        self.assertIn("openai/gpt-6.1-sol", combined)
        self.assertIn("openai/gpt-6-luna", combined)
        self.assertIn("xhigh", combined)
        self.assertIn("Fix all", combined)
        self.assertIn("non-bypassable", combined)
        self.assertIn("first forbidden push attempt", combined)
        self.assertIn("shell: restricted", combined)
        self.assertIn("auto-merge", combined)
        self.assertIn("credential", combined)


if __name__ == "__main__":
    unittest.main()
