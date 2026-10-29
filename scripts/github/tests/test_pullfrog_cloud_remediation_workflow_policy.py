import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates/starter-workflows/pullfrog-cloud-remediation-loop.yml"
LIVE = REPO_ROOT / ".github/workflows/pullfrog-cloud-remediation-loop.yml"
MANIFEST = REPO_ROOT / "templates/repo-workflow-materialization-manifest.json"
DOGFOOD_TRIGGER = REPO_ROOT / "templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml"
EXPECTED_HEADER = (
    "# Managed by templates/repo-workflow-materialization-manifest.json.\n"
    "# Edit templates/starter-workflows/pullfrog-cloud-remediation-loop.yml, then rematerialize the live workflow.\n"
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


class PullfrogCloudRemediationWorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")
        self.live = LIVE.read_text(encoding="utf-8")

    def test_template_and_live_workflow_are_byte_identical_and_registered(self):
        self.assertEqual(self.template, self.live)
        self.assertTrue(self.template.startswith(EXPECTED_HEADER))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn(
            {
                "source": "templates/starter-workflows/pullfrog-cloud-remediation-loop.yml",
                "target": ".github/workflows/pullfrog-cloud-remediation-loop.yml",
            },
            manifest["workflows"],
        )

    def test_pullfrog_source_changes_trigger_provider_free_dogfood(self):
        trigger = DOGFOOD_TRIGGER.read_text(encoding="utf-8")
        for pattern in [
            ".github/workflows/pullfrog*.yml",
            "templates/starter-workflows/pullfrog*.yml",
            "scripts/github/pullfrog_*.py",
            "scripts/github/validate_pullfrog_workflow.sh",
            "docs/pullfrog*.md",
        ]:
            self.assertIn(f"      - '{pattern}'\n", trigger)

    def test_dogfood_evidence_runs_for_every_non_stable_base(self):
        trigger = DOGFOOD_TRIGGER.read_text(encoding="utf-8")
        self.assertIn(
            "    branches:\n"
            "      - '**'\n"
            "      - '!main'\n"
            "      - '!master'\n",
            trigger,
        )
        self.assertNotIn("      - dev\n", trigger)

    def test_automatic_events_and_manual_exact_head_recovery_are_bounded(self):
        trigger = top_level_section(self.template, "on")
        keys = re.findall(r"^  ([a-zA-Z0-9_-]+):", trigger, flags=re.MULTILINE)
        self.assertEqual(keys, ["check_run", "workflow_run", "workflow_dispatch"])
        self.assertIn("      expected_head_sha:\n", trigger)
        self.assertNotIn("pull_request_target", trigger)
        self.assertNotRegex(trigger, r"(?m)^  push:")
        self.assertIn("pullfrog-cloud-remediation-", self.template)
        self.assertIn("github.event.check_run.check_suite.head_branch ||", self.template)
        self.assertIn("github.event.workflow_run.head_branch ||", self.template)
        self.assertIn("  cancel-in-progress: false", self.template)
        self.assertIn("timeout-minutes: 25", self.template)

    def test_provider_publish_and_auto_merge_permissions_are_separated(self):
        self.assertEqual(top_level_section(self.template, "permissions"), "  contents: read\n")
        self.assertEqual(self.template.count("      id-token: write\n"), 2)
        remediate = self.template.split("  remediate:\n", 1)[1].split("  validate:\n", 1)[0]
        validate = self.template.split("  validate:\n", 1)[1].split("  publish:\n", 1)[0]
        publish = self.template.split("  publish:\n", 1)[1].split("  rereview:\n", 1)[0]
        rereview = self.template.split("  rereview:\n", 1)[1].split("  validate_rereview:\n", 1)[0]
        validate_rereview = self.template.split("  validate_rereview:\n", 1)[1].split("  reconcile_threads:\n", 1)[0]
        reconcile = self.template.split("  reconcile_threads:\n", 1)[1].split("  rereview_gate:\n", 1)[0]
        rereview_gate = self.template.split("  rereview_gate:\n", 1)[1].split("  auto_merge_eligible:\n", 1)[0]
        auto_merge = self.template.split("  auto_merge_eligible:\n", 1)[1]
        self.assertIn("      id-token: write\n", remediate)
        self.assertIn("      contents: read\n", remediate)
        self.assertNotIn("contents: write", remediate)
        self.assertIn("          GH_TOKEN: ${{ github.token }}\n", remediate)
        self.assertIn("      contents: read\n", validate)
        self.assertNotIn("id-token: write", validate)
        self.assertNotIn("contents: write", validate)
        self.assertIn("      contents: read\n", publish)
        self.assertNotIn("id-token: write", publish)
        self.assertIn("      id-token: write\n", rereview)
        self.assertIn("      checks: read\n", rereview)
        self.assertNotIn("contents: write", rereview)
        self.assertNotIn("checks: write", rereview)
        self.assertIn("      checks: read\n", validate_rereview)
        self.assertIn("      pull-requests: read\n", validate_rereview)
        self.assertNotIn("id-token: write", validate_rereview)
        self.assertNotIn("contents: write", validate_rereview)
        self.assertNotIn("checks: write", validate_rereview)
        self.assertIn("      pull-requests: write\n", reconcile)
        self.assertIn("      checks: read\n", reconcile)
        self.assertNotIn("id-token: write", reconcile)
        self.assertNotIn("contents: write", reconcile)
        self.assertNotIn("checks: write", reconcile)
        self.assertIn("      checks: write\n", rereview_gate)
        self.assertNotIn("id-token: write", rereview_gate)
        self.assertNotIn("contents: write", rereview_gate)
        self.assertIn(
            "token: ${{ secrets.PULLFROG_REMEDIATION_PUBLISH_TOKEN }}", publish
        )
        self.assertIn("      contents: write\n", auto_merge)
        self.assertIn("      pull-requests: write\n", auto_merge)
        self.assertIn("      actions: write\n", auto_merge)
        self.assertNotIn("id-token: write", auto_merge)
        self.assertNotIn("PULLFROG_REMEDIATION_PUBLISH_TOKEN", auto_merge)
        self.assertNotIn("PULLFROG_REMEDIATION_PUBLISH_TOKEN", remediate)
        self.assertNotIn("PULLFROG_REMEDIATION_PUBLISH_TOKEN", validate)

    def test_pullfrog_is_native_pinned_and_has_no_remote_write_authority(self):
        self.assertIn(
            "uses: pullfrog/pullfrog@25a837a2b078177c3acdce790506d1fd1acedd82 # v0.1.102",
            self.template,
        )
        remediate = self.template.split("  remediate:\n", 1)[1].split("  validate:\n", 1)[0]
        rereview = self.template.split("  rereview:\n", 1)[1].split("  validate_rereview:\n", 1)[0]
        reconcile = self.template.split("  reconcile_threads:\n", 1)[1].split("  rereview_gate:\n", 1)[0]
        self.assertEqual(remediate.count("pullfrog/pullfrog@"), 1)
        self.assertEqual(rereview.count("pullfrog/pullfrog@"), 1)
        self.assertNotIn("pullfrog/pullfrog@", reconcile)
        self.assertEqual(self.template.count("pullfrog/pullfrog@"), 2)
        self.assertIn("          push: disabled\n", self.template)
        self.assertIn("          shell: restricted\n", self.template)
        self.assertIn("          progress_comments: disabled\n", self.template)
        self.assertIn("          GH_TOKEN: ${{ github.token }}\n", self.template)
        self.assertIn("output_schema:", self.template)
        self.assertIn("build-payload", self.template)
        self.assertIn("          prompt: ${{ steps.dispatch.outputs.payload }}\n", self.template)
        self.assertNotIn("prompt_file:", self.template)
        remediation = (REPO_ROOT / "scripts/github/pullfrog_cloud_remediation.py").read_text(encoding="utf-8")
        self.assertIn('"trigger": "fix_review"', remediation)
        self.assertIn('"approved_only": False', remediation)
        self.assertIn('"issue_number": identity["pr_number"]', remediation)
        self.assertIn('"review_id": claim["review_id"]', remediation)
        self.assertNotIn("ELEVATED_GITHUB_TOKEN", self.template)
        self.assertEqual(
            self.template.count(
                "${{ secrets.PULLFROG_REMEDIATION_PUBLISH_TOKEN }}"
            ),
            1,
        )

    def test_provider_uses_job_scoped_token_instead_of_minting_write_credentials(self):
        remediate = self.template.split("  remediate:\n", 1)[1].split("  validate:\n", 1)[0]
        self.assertIn("      pull-requests: read\n", remediate)
        self.assertIn("      contents: read\n", remediate)
        self.assertIn("          GH_TOKEN: ${{ github.token }}\n", remediate)
        self.assertNotIn("checks: write", remediate)
        self.assertNotIn("pull-requests: write", remediate)
        self.assertNotIn("contents: write", remediate)

    def test_published_fix_gets_one_scoped_exact_head_sol_rereview_and_gate(self):
        publish = self.template.split("  publish:\n", 1)[1].split("  rereview:\n", 1)[0]
        rereview = self.template.split("  rereview:\n", 1)[1].split(
            "  validate_rereview:\n", 1
        )[0]
        validate_rereview = self.template.split("  validate_rereview:\n", 1)[1].split(
            "  reconcile_threads:\n", 1
        )[0]
        reconcile = self.template.split("  reconcile_threads:\n", 1)[1].split(
            "  rereview_gate:\n", 1
        )[0]
        gate = self.template.split("  rereview_gate:\n", 1)[1].split(
            "  auto_merge_eligible:\n", 1
        )[0]
        self.assertIn("result_head_sha: ${{ steps.terminal.outputs.result_head_sha }}", publish)
        self.assertIn("github.run_attempt == 1", rereview)
        self.assertIn("needs.publish.outputs.result_head_sha", rereview)
        self.assertIn("needs.evaluate.outputs.base_sha", rereview)
        self.assertIn("Mint least-privilege Pullfrog re-review token", rereview)
        self.assertIn("mint-review-token", rereview)
        self.assertIn("Revoke least-privilege Pullfrog re-review token", rereview)
        self.assertIn("revoke-review-token", rereview)
        self.assertNotIn("verify-rereview-result", rereview)
        self.assertIn("          model: openai/gpt-sol\n", rereview)
        self.assertIn("          effort: xhigh\n", rereview)
        self.assertIn("          push: disabled\n", rereview)
        self.assertIn("          shell: restricted\n", rereview)
        self.assertIn("pullfrog-exact-head-rereview-result.v1", rereview)
        self.assertIn("pullfrog-exact-head-rereview-raw-${{ github.run_id }}", rereview)
        self.assertNotIn("openai/gpt-astra", rereview)
        self.assertIn("verify-rereview-result", validate_rereview)
        self.assertIn("github.run_attempt > 1", validate_rereview)
        self.assertIn(
            "pullfrog-exact-head-rereview-${{ github.run_id }}-a${{ github.run_attempt }}",
            validate_rereview,
        )
        self.assertNotIn("pullfrog/pullfrog@", validate_rereview)
        self.assertNotIn("id-token: write", validate_rereview)
        self.assertIn("reconcile-rereview-threads", reconcile)
        self.assertIn(
            "pullfrog-rereview-thread-reconciliation-${{ github.run_id }}-a${{ github.run_attempt }}",
            reconcile,
        )
        self.assertIn("      pull-requests: write\n", reconcile)
        self.assertNotIn("pullfrog/pullfrog@", reconcile)
        self.assertNotIn("id-token: write", reconcile)
        self.assertIn("publish-rereview-gate", gate)
        self.assertIn("reconciliation.json", gate)
        self.assertIn("      checks: write\n", gate)
        self.assertNotIn("pullfrog/pullfrog@", gate)
        self.assertNotIn("id-token: write", gate)

    def test_provider_output_is_untrusted_until_a_fresh_validation_job_seals_it(self):
        remediate = self.template.split("  remediate:\n", 1)[1].split("  validate:\n", 1)[0]
        validate = self.template.split("  validate:\n", 1)[1].split("  publish:\n", 1)[0]
        self.assertNotIn("Checkout trusted coordinator source", remediate)
        self.assertNotIn("scripts/github/pullfrog_cloud_remediation.py", remediate)
        self.assertIn("Capture untrusted provider output", remediate)
        self.assertIn("Persist untrusted provider bundle", remediate)
        self.assertIn("Checkout fresh trusted coordinator source", validate)
        self.assertIn("Checkout fresh exact source for validation", validate)
        self.assertIn("validate-candidate", validate)
        self.assertIn("Persist sealed patch bundle", validate)
        self.assertIn("GIT_CONFIG_NOSYSTEM: '1'", remediate)
        self.assertIn("GIT_NO_REPLACE_OBJECTS: '1'", remediate)
        self.assertIn("unsafe_provider_git_directory", remediate)
        self.assertIn("candidate_patch_too_large", remediate)
        self.assertIn("action_result_too_large", remediate)

    def test_all_actions_are_immutable_pins(self):
        uses = re.findall(r"^\s+uses:\s+([^\s#]+)", self.template, flags=re.MULTILINE)
        self.assertGreaterEqual(len(uses), 10)
        for use in uses:
            self.assertRegex(use, r"@[0-9a-f]{40}$")
        self.assertIn(
            "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
            uses,
        )
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            uses,
        )

    def test_claim_precedes_provider_and_terminal_receipt_follows_publish(self):
        claim_upload = self.template.index("Persist claim before provider invocation")
        dispatch_upload = self.template.index("Persist transient sealed dispatch")
        provider = self.template.index("Run Pullfrog without remote write authority")
        validator = self.template.index("Re-read exact head and seal trusted candidate")
        publish = self.template.index("Push one fast-forward commit to the exact PR branch")
        terminal = self.template.index("Persist terminal receipt")
        self.assertLess(claim_upload, provider)
        self.assertLess(dispatch_upload, provider)
        self.assertLess(provider, validator)
        self.assertLess(validator, publish)
        self.assertLess(provider, publish)
        self.assertLess(publish, terminal)
        self.assertIn("retention-days: 90", self.template)
        self.assertIn("load-history", self.template)
        self.assertIn("prepare-claim", self.template)
        self.assertIn(
            "--history-out artifacts/pullfrog-remediation/evaluate/history.json",
            self.template,
        )
        self.assertIn(
            "--history artifacts/pullfrog-remediation/evaluate/history.json",
            self.template,
        )
        self.assertNotIn(
            "--history artifacts/pullfrog-remediation/evaluate/ledger.json",
            self.template,
        )

    def test_durable_claim_artifact_contains_only_the_ledger_record(self):
        evaluate = self.template.split("  evaluate:\n", 1)[1].split(
            "  remediate:\n", 1
        )[0]
        self.assertIn(
            "          path: artifacts/pullfrog-remediation/claim/claim.json\n",
            evaluate,
        )
        self.assertIn("Persist transient sealed dispatch", evaluate)
        self.assertIn(
            "          path: artifacts/pullfrog-remediation/claim/payload.json\n",
            evaluate,
        )
        self.assertIn("dispatch_artifact: ${{ steps.claim.outputs.dispatch_artifact }}", evaluate)
        remediate = self.template.split("  remediate:\n", 1)[1].split(
            "  validate:\n", 1
        )[0]
        self.assertIn("Download transient sealed native dispatch", remediate)
        self.assertIn("name: ${{ needs.evaluate.outputs.dispatch_artifact }}", remediate)

    def test_failure_paths_always_emit_terminal_evidence_before_failing_closed(self):
        remediate = self.template.split("  remediate:\n", 1)[1].split("  validate:\n", 1)[0]
        validate = self.template.split("  validate:\n", 1)[1].split("  publish:\n", 1)[0]
        publish = self.template.split("  publish:\n", 1)[1].split("  auto_merge_eligible:\n", 1)[0]
        self.assertIn("        if: always()\n", remediate)
        self.assertIn("Persist untrusted provider bundle", remediate)
        self.assertIn("        continue-on-error: true\n", validate)
        self.assertIn(
            "        if: always() && steps.candidate.outputs.ready != 'true'\n",
            validate,
        )
        self.assertIn(
            "        if: always() && steps.apply.outcome == 'success'\n",
            publish,
        )
        self.assertIn(
            "        if: always() && steps.apply.outcome != 'success'\n",
            publish,
        )
        terminal_upload = publish.index("Persist terminal receipt")
        enforcement = publish.index("Enforce exact-head publication result")
        self.assertLess(terminal_upload, enforcement)

    def test_exact_head_is_re_read_and_push_is_compare_and_swap(self):
        self.assertIn("Re-read exact head immediately before Pullfrog", self.template)
        self.assertIn("Re-read exact head and seal trusted candidate", self.template)
        self.assertGreaterEqual(self.template.count("verify-head"), 2)
        self.assertIn(
            'git push origin "HEAD:refs/heads/${{ steps.apply.outputs.head_ref }}"',
            self.template,
        )
        self.assertNotIn("--force", self.template)
        self.assertNotIn("force-with-lease", self.template)
        self.assertIn("persist-credentials: false", self.template)
        self.assertEqual(self.template.count("persist-credentials: true"), 1)
        self.assertIn(
            "--candidate artifacts/pullfrog-remediation/candidate/candidate.json",
            self.template,
        )

    def test_publisher_push_uses_separate_event_emitting_credential(self):
        publish = self.template.split("  publish:\n", 1)[1].split("  auto_merge_eligible:\n", 1)[0]
        checkout = publish.split(
            "      - name: Checkout exact source with publication credential\n", 1
        )[1].split("\n      - name:", 1)[0]
        self.assertIn(
            "token: ${{ secrets.PULLFROG_REMEDIATION_PUBLISH_TOKEN }}", checkout
        )
        self.assertIn("persist-credentials: true", checkout)
        self.assertIn("normal PR", checkout)
        self.assertIn("synchronize event", checkout)
        self.assertIn("Pullfrog, CI, and Speculoos", checkout)
        self.assertNotIn("github.token", checkout)

    def test_custom_auto_merge_is_exact_head_and_main_master_remain_blocked(self):
        for forbidden in [
            "gh pr merge",
            "enablePullRequestAutoMerge",
            "mergePullRequest",
            "delete_branch",
            "gh release",
            "workflow_dispatches",
            "repository_dispatches",
        ]:
            self.assertNotIn(forbidden, self.template)
        auto_merge = self.template.split("  auto_merge_eligible:\n", 1)[1]
        self.assertIn(
            "name: Auto-merge clean exact-head PR to eligible non-stable base",
            auto_merge,
        )
        self.assertIn("needs.evaluate.outputs.reason == 'clean'", auto_merge)
        self.assertIn("scripts/github/pullfrog_dev_auto_merge.py", auto_merge)
        self.assertIn("      checks: read\n", auto_merge)
        self.assertIn(
            '--expected-head-sha "${{ needs.evaluate.outputs.source_head_sha }}"',
            auto_merge,
        )
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", auto_merge)
        script = (REPO_ROOT / "scripts/github/pullfrog_dev_auto_merge.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('FORBIDDEN_BASE_REFS = frozenset({"main", "master"})', script)
        self.assertNotIn("ALLOWED_BASE_REF", script)
        self.assertIn('DEV_AUTOMATION_REF = "dev"', script)
        self.assertIn('base_ref in FORBIDDEN_BASE_REFS', script)
        self.assertIn('identity["base_ref"] != DEV_AUTOMATION_REF', script)
        self.assertIn("def push_exact_merge", script)
        self.assertIn('"exact-old-oid-normal-fast-forward-push"', script)
        self.assertIn("def _receive_pack_body", script)
        self.assertIn('"merge-tree"', script)
        self.assertIn('AutoMergeError("base_compare_and_swap_failed")', script)
        self.assertNotIn('"--force"', script)
        self.assertNotIn('"--force-with-lease"', script)
        self.assertNotIn("/pulls/{identity['pr_number']}/merge", script)
        self.assertIn("cross-repo-workflow-updater-manual-trigger.yml", script)
        self.assertIn("sync-starter-workflow-template-refs-trigger.yml", script)
        remediation = (REPO_ROOT / "scripts/github/pullfrog_cloud_remediation.py").read_text(encoding="utf-8")
        self.assertIn("- Approval: `false`", remediation)
        self.assertIn("- Merge: `false`", remediation)


if __name__ == "__main__":
    unittest.main()
