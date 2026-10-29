import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates/starter-workflows/pullfrog-review-fallback.yml"
LIVE = REPO_ROOT / ".github/workflows/pullfrog-review-fallback.yml"
PRIMARY_TEMPLATE = REPO_ROOT / "templates/starter-workflows/pullfrog.yml"
PRIMARY_LIVE = REPO_ROOT / ".github/workflows/pullfrog.yml"
MANIFEST = REPO_ROOT / "templates/repo-workflow-materialization-manifest.json"
EXPECTED_HEADER = (
    "# Managed by templates/repo-workflow-materialization-manifest.json.\n"
    "# Edit templates/starter-workflows/pullfrog-review-fallback.yml, then rematerialize the live workflow.\n"
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


class PullfrogReviewFallbackWorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")
        self.live = LIVE.read_text(encoding="utf-8")
        self.primary = PRIMARY_TEMPLATE.read_text(encoding="utf-8")

    def test_materialization_is_registered_and_byte_identical(self):
        self.assertEqual(self.template, self.live)
        self.assertTrue(self.template.startswith(EXPECTED_HEADER))
        self.assertEqual(PRIMARY_TEMPLATE.read_bytes(), PRIMARY_LIVE.read_bytes())
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn(
            {
                "source": "templates/starter-workflows/pullfrog-review-fallback.yml",
                "target": ".github/workflows/pullfrog-review-fallback.yml",
            },
            manifest["workflows"],
        )

    def test_primary_is_explicitly_sol_xhigh_and_review_only(self):
        self.assertIn("          model: openai/gpt-sol\n", self.primary)
        self.assertIn("          effort: xhigh\n", self.primary)
        self.assertIn("          push: disabled\n", self.primary)
        self.assertIn("          shell: restricted\n", self.primary)
        self.assertNotIn("openai/gpt-astra", self.primary)

    def test_fallback_trigger_is_inert_without_explicit_activation(self):
        trigger = top_level_section(self.template, "on")
        keys = re.findall(r"^  ([a-zA-Z0-9_-]+):", trigger, flags=re.MULTILINE)
        self.assertEqual(keys, ["check_run", "workflow_dispatch"])
        self.assertIn("      authorize_fallback:\n", trigger)
        self.assertIn("        default: false\n", trigger)
        evaluate = self.template.split("  evaluate:\n", 1)[1].split("  gate_initial:\n", 1)[0]
        fallback = self.template.split("  fallback:\n", 1)[1].split("  finalize:\n", 1)[0]
        self.assertNotIn("PULLFROG_REVIEW_FALLBACK_ENABLED", evaluate)
        self.assertIn("vars.PULLFROG_REVIEW_FALLBACK_ENABLED == 'true'", fallback)
        self.assertIn("github.event.check_run.app.slug == 'pullfrog'", self.template)
        self.assertIn("github.event.check_run.name == 'pullfrog'", self.template)
        self.assertNotIn("pull_request_target", trigger)
        self.assertNotRegex(trigger, r"(?m)^  push:")

    def test_jobs_isolate_read_review_and_gate_write_authority(self):
        self.assertEqual(top_level_section(self.template, "permissions"), "  contents: read\n")
        self.assertRegex(
            self.template,
            r"(?s)  evaluate:.*?    permissions:\n      actions: read\n      checks: read\n      contents: read\n      pull-requests: read\n",
        )
        self.assertRegex(
            self.template,
            r"(?s)  gate_initial:.*?    permissions:\n      checks: write\n      contents: read\n      pull-requests: read\n",
        )
        self.assertRegex(
            self.template,
            r"(?s)  fallback:.*?    permissions:\n      id-token: write\n      contents: read\n      pull-requests: read\n",
        )
        fallback_section = self.template.split("  fallback:\n", 1)[1].split("  finalize:\n", 1)[0]
        self.assertNotIn("checks: write", fallback_section)
        self.assertNotIn("contents: write", fallback_section)
        self.assertNotIn("actions: write", fallback_section)
        self.assertNotRegex(fallback_section, r"\$\{\{\s*secrets\.")
        self.assertNotIn("PULLFROG_REMEDIATION_PUBLISH_TOKEN", self.template)
        self.assertIn("          GH_TOKEN: ${{ steps.review_token.outputs.credential }}\n", fallback_section)
        self.assertNotIn("          GH_TOKEN: ${{ github.token }}\n", fallback_section)

    def test_single_fallback_is_astra_xhigh_with_structured_output(self):
        self.assertEqual(self.template.count("uses: pullfrog/pullfrog@"), 1)
        self.assertIn("          model: openai/gpt-astra\n", self.template)
        self.assertIn("          effort: xhigh\n", self.template)
        self.assertIn("          push: disabled\n", self.template)
        self.assertIn("          shell: restricted\n", self.template)
        self.assertIn("pullfrog-review-fallback-result.v1", self.template)
        self.assertIn("          cwd: source\n", self.template)
        self.assertIn("Seal trusted preflight outside candidate workspace", self.template)
        self.assertIn('"$RUNNER_TEMP/pullfrog_review_contract.py"', self.template)
        self.assertIn('python "$RUNNER_TEMP/pullfrog_review_fallback.py" verify-identity', self.template)
        self.assertIn("\"additionalProperties\":false", self.template)
        self.assertIn("needs.evaluate.outputs.status == 'fallback_ready'", self.template)
        self.assertIn("needs.evaluate.outputs.status != 'ignored_fallback_run'", self.template)
        self.assertIn("cancel-in-progress: false", self.template)
        self.assertIn("      github.run_attempt == 1 &&\n", self.template)
        self.assertIn('            --run-attempt "$GITHUB_RUN_ATTEMPT" \\\n', self.template)

    def test_provider_uses_one_scoped_pullfrog_app_lease_and_revokes_it(self):
        fallback_section = self.template.split("  fallback:\n", 1)[1].split("  finalize:\n", 1)[0]
        self.assertIn("Mint least-privilege Pullfrog review token", fallback_section)
        self.assertIn("mint-review-token", fallback_section)
        self.assertIn("Revoke least-privilege Pullfrog review token", fallback_section)
        self.assertIn("revoke-review-token", fallback_section)
        self.assertIn("TOKEN_REVOCATION_OUTCOME", fallback_section)
        self.assertIn("token-revocation-outcome.txt", fallback_section)
        self.assertIn("token-lease.json", fallback_section)
        self.assertNotIn("checks: write", fallback_section)
        self.assertNotIn("actions: write", fallback_section)
        self.assertNotIn("contents: write", fallback_section)

    def test_failed_job_rerun_skips_provider_but_can_recover_finalization(self):
        fallback_section = self.template.split("  fallback:\n", 1)[1].split("  finalize:\n", 1)[0]
        finalize_section = self.template.split("  finalize:\n", 1)[1]
        self.assertIn("github.run_attempt == 1", fallback_section)
        self.assertIn("needs.gate_initial.result == 'success'", finalize_section)
        self.assertIn(
            "(needs.fallback.result != 'skipped' || github.run_attempt > 1)",
            finalize_section,
        )
        self.assertIn("token-revocation-outcome-file", finalize_section)

    def test_custom_gate_is_exact_head_and_not_the_raw_primary_check(self):
        self.assertIn("pullfrog-review-gate", self.template)
        self.assertIn("publish-gate", self.template)
        self.assertIn("verify-fallback-result", self.template)
        self.assertIn("verify-identity", self.template)
        self.assertIn("needs.evaluate.outputs.head_sha", self.template)
        self.assertNotIn("gh pr merge", self.template)
        self.assertNotIn("git push", self.template)
        self.assertNotIn("force-with-lease", self.template)

    def test_every_third_party_action_is_immutably_pinned(self):
        uses = re.findall(r"^\s+uses:\s+([^\s#]+)", self.template, flags=re.MULTILINE)
        self.assertGreater(len(uses), 0)
        for use in uses:
            self.assertRegex(use, r"@[0-9a-f]{40}$")
        self.assertIn(
            "pullfrog/pullfrog@25a837a2b078177c3acdce790506d1fd1acedd82",
            uses,
        )

    def test_only_bounded_results_cross_provider_boundary(self):
        self.assertIn("action-outcome.txt", self.template)
        self.assertIn("action-result.json", self.template)
        self.assertIn("retention-days: 7", self.template)
        self.assertNotIn("remediation.patch", self.template)
        self.assertNotIn("snapshot.json", self.template)
        self.assertNotIn("review_comments", self.template)

    def test_provider_preflight_failures_still_finalize_the_gate(self):
        self.assertRegex(
            self.template,
            r"(?s)- name: Download bounded untrusted fallback result\n"
            r"        continue-on-error: true\n"
            r"        uses: actions/download-artifact@[0-9a-f]{40}",
        )
        self.assertRegex(
            self.template,
            r"(?s)- name: Validate structured result and exact-head Pullfrog review\n"
            r"        id: validate\n"
            r"        continue-on-error: true\n",
        )
        self.assertRegex(
            self.template,
            r"(?s)- name: Finalize composite exact-head gate\n"
            r"        if: always\(\)\n",
        )


if __name__ == "__main__":
    unittest.main()
