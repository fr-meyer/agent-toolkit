from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from scripts.coderabbit.agent_command_policy import validate_agent_command
from scripts.coderabbit.normalize_threads import is_actionable_thread, is_coderabbit_author
from scripts.github.cross_repo_workflow_updater import (
    StarterTemplateHistory,
    apply_managed_updates,
    classify_binding_preview,
)


ROOT = Path(__file__).resolve().parents[1]
REUSABLE = ROOT / "templates/reusable-workflows/coderabbit-pr-automation.yml"
LIVE_REUSABLE = ROOT / ".github/workflows/coderabbit-pr-automation.yml"
STARTERS = [
    ROOT / "templates/starter-workflows/coderabbit-pr-automation-pr-trigger.yml",
    ROOT / "templates/starter-workflows/coderabbit-pr-automation-manual-trigger.yml",
    ROOT / "templates/starter-workflows/coderabbit-pr-comment-trigger.yml",
]
COMMENT_LIVE = ROOT / ".github/workflows/coderabbit-pr-comment-trigger.yml"


class CodeRabbitWorkflowContractTests(unittest.TestCase):
    def test_live_and_canonical_materialized_copies_match(self) -> None:
        self.assertEqual(REUSABLE.read_text(encoding="utf-8"), LIVE_REUSABLE.read_text(encoding="utf-8"))
        self.assertEqual(STARTERS[2].read_text(encoding="utf-8"), COMMENT_LIVE.read_text(encoding="utf-8"))

    def test_workflow_has_read_only_default_and_explicit_write_guards(self) -> None:
        reusable = REUSABLE.read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-latest", reusable)
        self.assertIn("timeout-minutes: 30", reusable)
        self.assertIn("contents: read", reusable)
        self.assertNotIn("contents: write", reusable)
        self.assertNotIn("runner_labels_json", reusable)
        self.assertIn("auto_commit/auto_push requires run_validation=true", reusable)
        self.assertIn('PUSH_TOKEN="${ELEVATED_GITHUB_TOKEN:-}"', reusable)
        self.assertNotIn('PUSH_TOKEN="$GITHUB_TOKEN"', reusable)

        for starter in STARTERS:
            text = starter.read_text(encoding="utf-8")
            self.assertNotIn("CODERABBIT_RUNNER_LABELS_JSON", text)
            self.assertNotIn("runner_labels_json:", text)
            self.assertNotIn("contents: write", text)
            self.assertIn("ELEVATED_GITHUB_TOKEN", text)

    def test_push_path_requires_explicit_elevated_token(self) -> None:
        reusable = REUSABLE.read_text(encoding="utf-8")
        push_section = reusable[reusable.index("Classify push credential requirements") :]
        self.assertIn("requires_elevated_github_token=true", push_section)
        self.assertIn("ELEVATED_GITHUB_TOKEN", push_section)
        self.assertIn("default GITHUB_TOKEN is read-only", push_section)
        self.assertNotIn('PUSH_TOKEN="$GITHUB_TOKEN"', push_section)

    def test_pinned_refs_and_shared_repository_ref_stay_aligned(self) -> None:
        pattern = re.compile(
            r"uses:\s*fr-meyer/agent-toolkit/\.github/workflows/coderabbit-pr-automation\.yml@([0-9a-f]{40})"
        )
        shared_pattern = re.compile(r"shared_repository_ref:\s*([0-9a-f]{40})")
        refs = []
        for starter in STARTERS:
            text = starter.read_text(encoding="utf-8")
            uses = pattern.findall(text)
            shared = shared_pattern.findall(text)
            self.assertEqual(uses, shared, starter)
            self.assertEqual(len(uses), 1, starter)
            refs.extend(uses)
        self.assertEqual(len(set(refs)), 1)


class CodeRabbitInputGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_author = {
            "login": "coderabbitai",
            "type": "Bot",
            "resourcePath": "/apps/coderabbitai",
            "url": "https://github.com/apps/coderabbitai",
        }

    def test_only_expected_coderabbit_identity_is_accepted(self) -> None:
        self.assertTrue(is_coderabbit_author(self.valid_author))
        for key, value in (("login", "someone-else"), ("__typename", "User"), ("resourcePath", "/apps/other")):
            author = dict(self.valid_author)
            author[key] = value
            self.assertFalse(is_coderabbit_author(author))

    def test_unresolved_current_root_thread_is_actionable_only_with_a_path(self) -> None:
        thread = {
            "isResolved": False,
            "isOutdated": False,
            "path": "src/example.py",
            "comments": {"nodes": [{"author": self.valid_author, "body": "Fix this"}]},
        }
        self.assertTrue(is_actionable_thread(thread))
        for change in (
            {"isResolved": True},
            {"isOutdated": True},
            {"path": ""},
            {"comments": {"nodes": [{"author": {"login": "other"}}]}},
        ):
            candidate = dict(thread)
            candidate.update(change)
            self.assertFalse(is_actionable_thread(candidate))

    def test_review_summary_inline_comment_suppression_and_fork_skip_contract(self) -> None:
        comment_trigger = (ROOT / "templates/starter-workflows/coderabbit-pr-comment-trigger.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.review.state == 'commented'", comment_trigger)
        self.assertIn("reviews/$REVIEW_ID/comments", comment_trigger)
        self.assertIn("head.repo.fork", comment_trigger)
        self.assertIn("should_run=false", comment_trigger)

    def test_zero_issue_and_missing_agent_paths_remain_explicit(self) -> None:
        reusable = REUSABLE.read_text(encoding="utf-8")
        orchestrator = (ROOT / "scripts/coderabbit/orchestrate_core.py").read_text(encoding="utf-8")
        agent_runner = (ROOT / "scripts/coderabbit/run_agent_pass_core.py").read_text(encoding="utf-8")
        self.assertIn("steps.issue_count.outputs.count != '0'", reusable)
        self.assertIn("no_actionable_work", orchestrator)
        self.assertIn("status': 'not_configured'", agent_runner)

    def test_agent_command_entrypoint_is_allowlisted(self) -> None:
        self.assertIsNone(validate_agent_command(["agent", "--prompt", "{prompt_path}"]))
        self.assertIsNone(validate_agent_command(["/opt/tools/cursor-agent", "--prompt", "x"]))
        self.assertIsNotNone(validate_agent_command(["bash", "-lc", "echo unsafe"]))
        self.assertIsNotNone(validate_agent_command(["python3", "unsafe.py"]))


class ConsumerDistributionGuardTests(unittest.TestCase):
    def test_diverged_consumer_workflow_is_not_overwritten(self) -> None:
        binding = {
            "starterTemplate": "templates/starter-workflows/coderabbit-pr-comment-trigger.yml",
            "targetPath": ".github/workflows/coderabbit-pr-comment-trigger.yml",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            consumer = Path(temp_dir)
            target = consumer / binding["targetPath"]
            target.parent.mkdir(parents=True)
            original = "name: locally customized\n"
            target.write_text(original, encoding="utf-8")

            preview = classify_binding_preview(ROOT, consumer, binding, StarterTemplateHistory(ROOT))
            self.assertEqual(preview.status, "diverged")
            self.assertEqual(apply_managed_updates(ROOT, consumer, [preview]), [])
            self.assertEqual(target.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
