"""Real-Git tests for the staged per-PR contract; legacy gate stays untouched."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "speculoos_per_pr_contract.py"
spec = importlib.util.spec_from_file_location("speculoos_per_pr_staged", SOURCE)
assert spec and spec.loader
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

TASK = "staged-public-canary"
HEAD_REF = "test/staged-public-canary"
DOC = "docs/staged-public-canary.md"
TASK_PATH = f"specs/{TASK}/task.yaml"
BODY_PATH = f"specs/{TASK}/pr-body.md"
MESSAGE_PATH = f"specs/{TASK}/commit-message.txt"
UNICODE_DOC = "docs/café.md"


class PerPrStagingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "candidate"
        self.trusted = Path(tmp.name) / "trusted"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "dev")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.write(".speculoos/manifest.yaml", "current_task: unrelated-global-task\n")
        self.write("obsolete.txt", "old public fixture\n")
        self.write(".speculoos/actors.json", json.dumps({
            "branch_policies": [{"name": "feature_to_non_stable", "auto_merge": {
                "enabled": True, "forbidden_base_refs": ["main", "master"],
                "required_evidence": sorted(contract.REQUIRED_EVIDENCE)}}],
            "profiles": {"github_actions_non_stable_auto_merge": {
                "same_repository_required": True, "force_push_allowed": False}},
        }))
        self.write("templates/starter-workflows/speculoos-trusted-canary.yml", "name: trusted\n")
        self.write(".github/workflows/speculoos-trusted-canary.yml", "name: trusted\n")
        self.write("templates/starter-workflows/speculoos.yml", "name: legacy\n")
        self.write(".github/workflows/speculoos.yml", "name: legacy\n")
        self.write("templates/repo-workflow-materialization-manifest.json", json.dumps({
            "workflows": [{"source": "templates/starter-workflows/speculoos-trusted-canary.yml",
                           "target": ".github/workflows/speculoos-trusted-canary.yml"},
                          {"source": "templates/starter-workflows/speculoos.yml",
                           "target": ".github/workflows/speculoos.yml"}]}))
        self.write("scripts/github/speculoos_per_pr_contract.py", SOURCE.read_text())
        self.git("add", ".")
        self.git("commit", "-q", "-m", "trusted base")
        self.base = self.git("rev-parse", "HEAD")
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(self.repo), str(self.trusted)],
                       check=True, capture_output=True)
        self.git("update-ref", "refs/remotes/origin/dev", self.base)
        self.git("checkout", "-q", "-b", HEAD_REF)
        self.write(DOC, "# Staged public canary\n")
        self.write(TASK_PATH, f"id: {TASK}\nbranch: {HEAD_REF}\nbase_branch: dev\n"
                              "delivery_policy:\n  mode: inherit_branch_policy\n")
        self.write(MESSAGE_PATH, f"docs: {TASK}\n\nFeature PRs target `dev`. Release/promotion PRs target `main`.\n")
        self.packet()
        self.commit()

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                                capture_output=True, text=True)
        return result.stdout.strip()

    def write(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def write_bytes(self, path, content):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def packet(self, files=None):
        files = files or [DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH]
        listed = "\n".join(f"- `{p}`" for p in files)
        docs = "\n".join(f"`{p}`" for p in files if p.startswith("docs/"))
        self.write(BODY_PATH, f"# {TASK}\n\nFeature PRs target `dev`. Release/promotion PRs target `main`.\n\n"
                              f"## Changed Files For Publish\n\n{listed}\n\n"
                              f"## Documentation Impact\n\n{docs} records the canary.\n")

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "candidate")

    def report(self, **overrides):
        head = self.git("rev-parse", "HEAD")
        args = dict(
            repo=str(self.repo), trusted_repo=str(self.trusted), expected_trusted_sha=self.base,
            repo_slug="fr-meyer/agent-toolkit",
            expected_head_repo="fr-meyer/agent-toolkit", task=None, task_source="per-pr",
            expected_head_ref=HEAD_REF, expected_head_sha=head,
            expected_base_ref="dev", expected_base_sha=self.base, output=None)
        args.update(overrides)
        return contract.validate(Namespace(**args))

    def test_per_pr_task_ignores_unrelated_global_pointer(self):
        result = self.report()
        self.assertEqual(result["status"], "ok", result["blockers"])
        self.assertEqual(result["task"], TASK)
        self.assertEqual(result["task_source"], "per-pr")

    def test_packet_inventory_mismatch_fails_closed(self):
        self.packet([DOC, TASK_PATH, BODY_PATH])
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("changed_files_match" in b for b in result["blockers"]))

    def test_non_ascii_path_matches_inventory(self):
        self.write(UNICODE_DOC, "# Public example\n")
        self.packet([DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH, UNICODE_DOC])
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "ok", result["blockers"])

    def test_non_ascii_path_is_still_scanned(self):
        self.write(UNICODE_DOC, "ghp_" + "A" * 30 + "\n")
        self.packet([DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH, UNICODE_DOC])
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("private_data_scan" in b for b in result["blockers"]))

    def test_leading_colon_binary_path_is_not_mistaken_for_deletion(self):
        self.write_bytes(":foo", b"\x00ghp_" + b"A" * 30 + b"\n")
        self.packet([DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH, ":foo"])
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("private_data_scan" in b for b in result["blockers"]))

    def test_magic_pathspec_named_binary_file_is_not_skipped(self):
        path = ":(literal)foo"
        self.write_bytes(path, b"\x00ghp_" + b"A" * 30 + b"\n")
        self.packet([DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH, path])
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("private_data_scan" in b for b in result["blockers"]))

    def test_actual_deletion_remains_skippable(self):
        (self.repo / "obsolete.txt").unlink()
        self.packet([DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH, "obsolete.txt"])
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "ok", result["blockers"])

    def test_invalid_utf8_diff_returns_blocked_report(self):
        self.write_bytes(DOC, b"\xff\n")
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("not UTF-8" in b for b in result["blockers"]))

    def test_manifest_mode_uses_legacy_workflow_mapping(self):
        legacy_task = f".speculoos/tasks/{TASK}.yaml"
        self.write(".speculoos/manifest.yaml", f"current_task: {TASK}\n")
        self.write(legacy_task, f"id: {TASK}\nbranch: {HEAD_REF}\nbase_branch: dev\n"
                                "delivery_policy:\n  mode: inherit_branch_policy\n")
        self.packet([".speculoos/manifest.yaml", legacy_task, DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH])
        self.commit()
        result = self.report(task_source="manifest", task=TASK)
        self.assertEqual(result["status"], "ok", result["blockers"])
        self.assertTrue(any(c["name"] == "workflow_materialization" and c["status"] == "passed"
                            for c in result["checks"]))

    def test_manifest_mode_detects_candidate_workflow_drift(self):
        legacy_task = f".speculoos/tasks/{TASK}.yaml"
        template = "templates/starter-workflows/speculoos.yml"
        self.write(".speculoos/manifest.yaml", f"current_task: {TASK}\n")
        self.write(legacy_task, f"id: {TASK}\nbranch: {HEAD_REF}\nbase_branch: dev\n"
                                "delivery_policy:\n  mode: inherit_branch_policy\n")
        self.write(template, "name: drifted candidate\n")
        self.packet([".speculoos/manifest.yaml", legacy_task, DOC, TASK_PATH, BODY_PATH,
                     MESSAGE_PATH, template])
        self.commit()
        result = self.report(task_source="manifest", task=TASK)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any(c["name"] == "workflow_materialization" and c["status"] == "failed"
                            for c in result["checks"]))

    def test_missing_or_candidate_trusted_checkout_fails_closed(self):
        missing = self.report(trusted_repo="")
        self.assertEqual(missing["status"], "blocked")
        self.assertTrue(any("trusted checkout" in b for b in missing["blockers"]))
        candidate = self.report(trusted_repo=str(self.repo),
                                expected_trusted_sha=self.git("rev-parse", "HEAD"))
        self.assertEqual(candidate["status"], "blocked")
        self.assertTrue(any("cannot trust the candidate" in b for b in candidate["blockers"]))

    def test_wrong_trusted_sha_fails_closed(self):
        result = self.report(expected_trusted_sha="0" * 40)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("exact_trusted_identity" in b for b in result["blockers"]))

    def test_stable_base_fails_closed(self):
        for base_ref in ("main", "master"):
            with self.subTest(base_ref=base_ref):
                self.git("update-ref", f"refs/remotes/origin/{base_ref}", self.base)
                result = self.report(expected_base_ref=base_ref)
                self.assertEqual(result["status"], "blocked")
                self.assertTrue(any("stable base" in b for b in result["blockers"]))

    def test_governed_workflow_change_fails_closed(self):
        self.write(".github/workflows/pullfrog.yml", "name: altered\n")
        self.commit()
        result = self.report()
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("governed" in b for b in result["blockers"]))

    def test_inherited_task_is_not_per_pr_evidence(self):
        task_text = (self.repo / TASK_PATH).read_text()
        self.git("checkout", "-q", "dev")
        self.write(TASK_PATH, task_text)
        self.git("add", TASK_PATH)
        self.git("commit", "-q", "-m", "inherit task")
        advanced_base = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/dev", advanced_base)
        self.git("checkout", "-q", HEAD_REF)
        result = self.report(expected_base_sha=advanced_base)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("per-PR task must be newly added" in b for b in result["blockers"]))
        self.assertTrue(any(c["name"] == "exact_git_identity" and c["status"] == "passed"
                            for c in result["checks"]))

    def test_legacy_workflow_and_validator_are_not_replaced(self):
        repo_root = SOURCE.parents[2]
        workflow = (repo_root / "templates/starter-workflows/speculoos.yml").read_text()
        self.assertIn("scripts/github/speculoos_pr_contract.py", workflow)
        self.assertIn("current_task", workflow)
        self.assertTrue((repo_root / "scripts/github/speculoos_pr_contract.py").is_file())


if __name__ == "__main__":
    unittest.main()
