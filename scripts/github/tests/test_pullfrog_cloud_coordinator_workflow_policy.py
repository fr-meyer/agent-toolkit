import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml"
LIVE = REPO_ROOT / ".github/workflows/pullfrog-cloud-coordinator-dry-run.yml"
PULLFROG_TEMPLATE = REPO_ROOT / "templates/starter-workflows/pullfrog.yml"
PULLFROG_LIVE = REPO_ROOT / ".github/workflows/pullfrog.yml"
MANIFEST = REPO_ROOT / "templates/repo-workflow-materialization-manifest.json"
SPECULOOS_MANIFEST = REPO_ROOT / ".speculoos/manifest.yaml"
ACTORS = REPO_ROOT / ".speculoos/actors.json"
PUBLISH_POLICY = REPO_ROOT / ".speculoos/publish-policy.yaml"
REVIEW_EVIDENCE = REPO_ROOT / ".speculoos/review-evidence.json"
EXPECTED_HEADER = (
    "# Managed by templates/repo-workflow-materialization-manifest.json.\n"
    "# Edit templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml, then rematerialize the live workflow.\n"
)


def top_level_section(text: str, name: str) -> str:
    lines = text.splitlines()
    start = lines.index(f"{name}:") + 1
    end = len(lines)
    for index in range(start, len(lines)):
        line = lines[index]
        if line and not line.startswith((" ", "#")):
            end = index
            break
    return "\n".join(lines[start:end])


class PullfrogCloudCoordinatorWorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")
        self.live = LIVE.read_text(encoding="utf-8")

    def test_template_and_live_workflow_are_byte_identical(self):
        self.assertEqual(self.template, self.live)
        self.assertTrue(self.template.startswith(EXPECTED_HEADER))
        self.assertEqual(PULLFROG_TEMPLATE.read_bytes(), PULLFROG_LIVE.read_bytes())

    def test_materialization_manifest_owns_the_live_workflow(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn(
            {
                "source": "templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml",
                "target": ".github/workflows/pullfrog-cloud-coordinator-dry-run.yml",
            },
            manifest["workflows"],
        )

    def test_triggers_are_evidence_events_and_manual_exact_head_only(self):
        trigger = top_level_section(self.template, "on")
        keys = re.findall(r"^  ([a-zA-Z0-9_-]+):", trigger, flags=re.MULTILINE)
        self.assertEqual(keys, ["check_run", "workflow_run", "workflow_dispatch"])
        self.assertIn("      - completed\n", trigger)
        self.assertIn("      expected_head_sha:\n", trigger)
        self.assertNotIn("pull_request_target", trigger)
        self.assertNotRegex(trigger, r"(?m)^  push:")

    def test_permissions_are_read_only_and_least_privilege(self):
        permissions = top_level_section(self.template, "permissions")
        self.assertEqual(
            permissions,
            "  checks: read\n  contents: read\n  pull-requests: read\n",
        )
        self.assertNotRegex(self.template, r"(?m)^\s+[a-z-]+:\s+write\s*$")

    def test_actions_are_immutable_and_governed(self):
        uses = re.findall(r"^\s+uses:\s+([^\s#]+)", self.template, flags=re.MULTILINE)
        self.assertEqual(
            uses,
            [
                "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
                "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
                "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            ],
        )
        for use in uses:
            self.assertRegex(use, r"@[0-9a-f]{40}$")

    def test_concurrency_and_time_are_bounded(self):
        concurrency = top_level_section(self.template, "concurrency")
        self.assertIn("pullfrog-cloud-coordinator-", concurrency)
        self.assertIn("  cancel-in-progress: false", concurrency)
        self.assertIn("    timeout-minutes: 10\n", self.template)

    def test_workflow_is_provider_free_and_cannot_mutate_repository(self):
        self.assertNotIn("pullfrog/pullfrog@", self.template)
        self.assertNotIn("ELEVATED_GITHUB_TOKEN", self.template)
        self.assertNotRegex(self.template, r"\$\{\{\s*secrets\.")
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", self.template)
        self.assertIn("--fail-on-stopped", self.template)
        self.assertIn("Evaluate exact-head evidence without mutation", self.template)
        for forbidden in [
            "git push",
            "gh pr merge",
            "gh run rerun",
            "workflow_dispatches",
            "repository_dispatches",
            "branches/",
            "releases",
            "deployments",
        ]:
            self.assertNotIn(forbidden, self.template)

    def test_only_sanitized_receipt_is_uploaded(self):
        self.assertIn("path: artifacts/pullfrog-cloud-coordinator/receipt.json", self.template)
        self.assertIn("if-no-files-found: error", self.template)
        self.assertIn("retention-days: 30", self.template)
        self.assertIn('--failure-receipt "$receipt"', self.template)
        self.assertIn("if: always() && steps.context.outcome == 'success'", self.template)
        self.assertNotIn("snapshot.json", self.template)
        self.assertNotIn("review_comments", self.template)

    def test_pullfrog_is_the_only_required_ai_reviewer(self):
        actors = json.loads(ACTORS.read_text(encoding="utf-8"))
        evidence = json.loads(REVIEW_EVIDENCE.read_text(encoding="utf-8"))
        manifest = SPECULOOS_MANIFEST.read_text(encoding="utf-8")
        publish_policy = PUBLISH_POLICY.read_text(encoding="utf-8")

        self.assertEqual(actors["defaults"]["review_actor"], "pullfrog_review")
        for branch in actors["branch_policies"]:
            self.assertEqual(branch["review_actor"], "pullfrog_review")
            self.assertFalse(branch["auto_merge"]["enabled"])
        self.assertEqual(actors["profiles"]["mergeguez_review"]["roles"], [])
        self.assertTrue(actors["profiles"]["pullfrog_review"]["required_for_merge"])
        self.assertFalse(actors["profiles"]["pullfrog_review"]["push_enabled"])

        requirements = evidence["requirements"]
        self.assertEqual(
            requirements["reviewer_groups"]["required_pr_review"]["primary"],
            ["pullfrog_review"],
        )
        self.assertIn("speculoos_evidence", requirements["required_sources"])
        self.assertEqual(
            requirements["reviewers"]["mergeguez_review"]["policy"], "disabled"
        )

        self.assertIn("  review_actor: pullfrog_review\n", manifest)
        self.assertRegex(
            manifest,
            r"(?s)mergeguez_review:\n\s+policy: disabled\b.*required_pr_review:.*primary:\n\s+- pullfrog_review\b",
        )
        self.assertIn("    - exact_head_pullfrog_review\n", publish_policy)
        self.assertNotIn("exact_head_mergeguez_review", publish_policy)


if __name__ == "__main__":
    unittest.main()
