"""Real-Git fixtures for the isolated, public per-PR Speculoos proposal."""

from __future__ import annotations

import importlib.util
import datetime
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from unittest import mock
from argparse import Namespace
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[3]
SCRIPT = SOURCE / "scripts/github/speculoos_per_pr_contract.py"
spec = importlib.util.spec_from_file_location("speculoos_pr_contract", SCRIPT)
assert spec and spec.loader
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
attestation_spec = importlib.util.spec_from_file_location(
    "speculoos_attestation_roundtrip", SOURCE / "scripts/github/pullfrog_speculoos_attestation.py")
assert attestation_spec and attestation_spec.loader
attestation = importlib.util.module_from_spec(attestation_spec)
attestation_spec.loader.exec_module(attestation)

TASK = "canary-public-evidence"
HEAD_REF = "test/speculoos-shadow-canary-public-evidence"
DOC = "docs/canary-public-evidence.md"
TASK_PATH = f"specs/{TASK}/task.yaml"
BODY_PATH = f"specs/{TASK}/pr-body.md"
MESSAGE_PATH = f"specs/{TASK}/commit-message.txt"


class PerPrContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "dev")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.write(".speculoos/manifest.yaml", "current_task: unrelated-global-task\n")
        actors = {
            "branch_policies": [{
                "name": "feature_to_non_stable",
                "auto_merge": {
                    "enabled": True,
                    "forbidden_base_refs": ["main", "master"],
                    "required_evidence": ["pullfrog", "pullfrog-approval", "ci", "speculoos", "destination-guard"],
                },
            }],
            "profiles": {"github_actions_non_stable_auto_merge": {
                "same_repository_required": True,
                "force_push_allowed": False,
            }},
        }
        self.write(".speculoos/actors.json", json.dumps(actors))
        workflow = (SOURCE / "templates/starter-workflows/speculoos-trusted-canary.yml").read_text()
        self.write("templates/starter-workflows/speculoos-trusted-canary.yml", workflow)
        self.write(".github/workflows/speculoos-trusted-canary.yml", workflow)
        self.write("templates/repo-workflow-materialization-manifest.json", json.dumps({
            "workflows": [{"source": "templates/starter-workflows/speculoos-trusted-canary.yml", "target": ".github/workflows/speculoos-trusted-canary.yml"}]
        }))
        self.write("scripts/github/speculoos_per_pr_contract.py", SCRIPT.read_text())
        self.git("add", ".")
        self.git("commit", "-q", "-m", "trusted base")
        self.base = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/dev", self.base)
        self.git("checkout", "-q", "-b", HEAD_REF)
        self.write(DOC, "# Canary\n\nPublic mention evidence.\n")
        self.write(TASK_PATH, f"id: {TASK}\nbranch: {HEAD_REF}\nbase_branch: dev\ndelivery_policy:\n  mode: inherit_branch_policy\n")
        self.write(MESSAGE_PATH, f"docs: validate {TASK}\n\nFeature PRs target `dev`. Release/promotion PRs target `main`.\n")
        self.write_packet()
        self.commit()

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True)
        return result.stdout.strip()

    def write(self, relative, content):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_packet(self, files=None, docs=DOC):
        if files is None:
            files = [DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH]
        lines = "\n".join(f"- `{path}`" for path in files)
        self.write(BODY_PATH, f"""# {TASK}

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Changed Files For Publish

{lines}

## Documentation Impact

`{docs}` records the canary.
""")

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "candidate")

    def report(self, **overrides):
        args = dict(repo=str(self.repo), trusted_repo=None, repo_slug="example/agent-toolkit",
                    expected_head_repo="example/agent-toolkit", task=None,
                    task_source="per-pr", expected_head_ref=HEAD_REF,
                    expected_head_sha=self.git("rev-parse", "HEAD"),
                    expected_base_ref="dev", expected_base_sha=self.base, output=None)
        args.update(overrides)
        return contract.validate(Namespace(**args))

    def assert_blocked(self, expected, **overrides):
        report = self.report(**overrides)
        self.assertEqual(report["status"], "blocked", report)
        self.assertIn(expected, "\n".join(report["blockers"]))

    def test_one_public_task_ignores_unrelated_global_manifest(self):
        report = self.report()
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(report["task"], TASK)
        self.assertEqual(len(report["checks"]), 11)

    def test_real_validator_report_roundtrips_through_run_and_head_check(self):
        report = self.report(repo_slug=attestation.REPO,
                             expected_head_repo=attestation.REPO)
        self.assertEqual(report["status"], "ok", report)
        report_raw = attestation._canonical(report) + b"\n"
        head_sha = self.git("rev-parse", "HEAD")
        source_sha = "c" * 40
        binding = attestation.produce(
            report_raw, repository_id=42, pr_number=106,
            head_ref=HEAD_REF, head_sha=head_sha, base_ref="dev",
            base_sha=self.base, source_sha=source_sha, run_id=111,
            run_attempt=2)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("contract.json", report_raw)
            archive.writestr("attestation.json", attestation._canonical(binding) + b"\n")
        raw = buffer.getvalue()
        now = datetime.datetime(2026, 11, 6, 12, 0, tzinfo=datetime.timezone.utc)
        instant = lambda offset: (now + datetime.timedelta(seconds=offset)).isoformat()
        artifact = {
            "id": 222, "name": f"speculoos-pr-106-{head_sha}-111-2",
            "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "expired": False, "expires_at": instant(3600),
            "workflow_run": {"id": 111, "repository_id": 42,
                             "head_repository_id": 42, "head_branch": HEAD_REF,
                             "head_sha": head_sha},
        }
        run = {"id": 111, "run_attempt": 2, "event": "pull_request_target",
               "path": attestation.WORKFLOW_PATH, "head_sha": head_sha,
               "head_branch": HEAD_REF, "status": "completed", "conclusion": "success",
               "created_at": instant(-86400), "run_started_at": instant(-120),
               "updated_at": instant(-60),
               "repository": {"id": 42, "full_name": attestation.REPO}}
        pr = {"number": 106, "state": "open",
              "head": {"ref": HEAD_REF, "sha": head_sha, "repo": {"id": 42}},
              "base": {"ref": "dev", "sha": self.base, "repo": {"id": 42}}}
        check = {"id": 333, "name": attestation.CHECK_NAME,
                 "head_sha": head_sha, "status": "completed",
                 "conclusion": "success",
                 "external_id": "speculoos:v1:" + binding["binding_digest"],
                 "app": {"id": 444}}
        paths = {
            f"/repos/{attestation.REPO}/pulls/106": pr,
            f"/repos/{attestation.REPO}/actions/runs/111": run,
            f"/repos/{attestation.REPO}/actions/artifacts/222": artifact,
            f"/repos/{attestation.REPO}/commits/{head_sha}/check-runs?per_page=100":
                {"total_count": 1, "check_runs": [check]},
        }
        class Client:
            def get(self, path):
                return json.loads(json.dumps(paths[path]))
        with mock.patch.object(attestation, "verify_signed_source"):
            receipt = attestation.collect_verified(
                Client(), lambda _: raw, pr_number=106, run_id=111,
                artifact_id=222, repository_id=42, trusted_app_id=444,
                expected_source_sha=source_sha, now=now.timestamp())
        self.assertEqual(receipt["status"], "verified")
        self.assertEqual(receipt["head_sha"], head_sha)
        self.assertEqual(receipt["run_attempt"], 2)

    def test_missing_per_pr_task_fails_closed(self):
        (self.repo / TASK_PATH).unlink()
        self.commit()
        self.assert_blocked("expected one changed per-PR task, found 0")

    def test_second_per_pr_task_fails_closed(self):
        self.write("specs/other/task.yaml", "id: other\n")
        self.commit()
        self.assert_blocked("expected one changed per-PR task, found 2")

    def test_inherited_existing_task_fails_closed(self):
        self.git("update-ref", "refs/remotes/origin/dev", self.git("rev-parse", "HEAD"))
        self.base = self.git("rev-parse", "HEAD")
        self.write(DOC, "# Revised\n")
        self.commit()
        self.assert_blocked("expected one changed per-PR task, found 0")

    def test_wrong_task_identity_fails_closed(self):
        self.write(TASK_PATH, f"id: other\nbranch: {HEAD_REF}\nbase_branch: dev\ndelivery_policy:\n  mode: inherit_branch_policy\n")
        self.commit()
        self.assert_blocked("task_identity")

    def test_duplicate_task_identity_fields_fail_closed(self):
        self.write(TASK_PATH, f"id: {TASK}\nid: other\nbranch: {HEAD_REF}\nbranch: other\nbase_branch: dev\ndelivery_policy:\n  mode: inherit_branch_policy\n")
        self.commit()
        self.assert_blocked("expected one top-level field: id")

    def test_duplicate_delivery_section_fails_closed(self):
        self.write(TASK_PATH, f"id: {TASK}\nbranch: {HEAD_REF}\nbase_branch: dev\ndelivery_policy:\n  mode: inherit_branch_policy\ndelivery_policy:\n  mode: bypass\n")
        self.commit()
        self.assert_blocked("expected one section: delivery_policy")

    def test_wrong_branch_fails_closed(self):
        self.write(TASK_PATH, f"id: {TASK}\nbranch: other\nbase_branch: dev\ndelivery_policy:\n  mode: inherit_branch_policy\n")
        self.commit()
        self.assert_blocked("task_identity")

    def test_packet_mismatch_fails_closed(self):
        self.write_packet(files=[DOC, TASK_PATH, BODY_PATH])
        self.commit()
        self.assert_blocked("changed_files_match")

    def test_missing_documentation_impact_fails_closed(self):
        self.write_packet(docs="docs/wrong.md")
        self.commit()
        self.assert_blocked("documentation_impact")

    def test_every_documentation_path_must_be_named_exactly(self):
        second = "docs/canary-public-evidence-extra.md"
        self.write(second, "# Additional public doc\n")
        self.write_packet(files=[DOC, second, TASK_PATH, BODY_PATH, MESSAGE_PATH], docs=second)
        self.commit()
        self.assert_blocked("documentation_impact")
        self.write_packet(files=[DOC, second, TASK_PATH, BODY_PATH, MESSAGE_PATH], docs=f"{DOC}` and `{second}")
        self.commit()
        self.assertEqual(self.report()["status"], "ok")

    def test_shared_policy_change_fails_closed(self):
        self.write(".speculoos/manifest.yaml", "current_task: canary-public-evidence\n")
        self.write_packet(files=[DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH, ".speculoos/manifest.yaml"])
        self.commit()
        self.assert_blocked("per-PR evidence cannot change governed policy or workflow surfaces")

    def test_governed_workflow_change_fails_closed(self):
        self.write(".github/workflows/speculoos-trusted-canary.yml", "name: replaced\n")
        self.commit()
        self.assert_blocked("per-PR evidence cannot change governed policy or workflow surfaces")

    def test_governed_authority_code_change_fails_closed(self):
        self.write("scripts/github/pullfrog_destination_guard.py", "print('changed')\n")
        self.commit()
        self.assert_blocked("per-PR evidence cannot change governed policy or workflow surfaces")

    def test_wrong_head_and_base_fail_closed(self):
        self.assert_blocked("exact_git_identity", expected_head_sha=self.base)
        self.assert_blocked("exact_git_identity", expected_base_sha=self.git("rev-parse", "HEAD"))

    def test_fork_head_fails_closed(self):
        self.assert_blocked("same-repository head", expected_head_repo="other/agent-toolkit")

    def test_symlink_task_fails_closed(self):
        (self.repo / TASK_PATH).unlink()
        (self.repo / TASK_PATH).symlink_to("commit-message.txt")
        self.commit()
        self.assert_blocked("missing or unsafe file")

    def test_added_line_starting_two_plus_signs_is_scanned(self):
        self.write(DOC, "# Canary\n++ghp_" + "A" * 20 + "\n")
        self.commit()
        self.assert_blocked("private_data_scan")

    def test_binary_changed_blob_fails_closed(self):
        binary = "fixtures/data.bin"
        path = self.repo / binary
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x00" + b"ghp_" + b"A" * 20 + b"\x00")
        self.write_packet(files=[DOC, binary, TASK_PATH, BODY_PATH, MESSAGE_PATH])
        self.commit()
        self.assert_blocked("private_data_scan")

    def test_scan_reads_committed_blob_even_if_worktree_is_replaced(self):
        path = self.repo / DOC
        path.write_bytes(b"\x00" + b"ghp_" + b"A" * 20 + b"\x00")
        self.commit()
        path.write_text("# Harmless working tree replacement\n", encoding="utf-8")
        self.assert_blocked("private_data_scan")

    def test_identity_reads_committed_task_not_worktree_replacement(self):
        self.write(TASK_PATH, f"id: other\nbranch: {HEAD_REF}\nbase_branch: dev\ndelivery_policy:\n  mode: inherit_branch_policy\n")
        self.commit()
        self.write(TASK_PATH, f"id: {TASK}\nbranch: {HEAD_REF}\nbase_branch: dev\ndelivery_policy:\n  mode: inherit_branch_policy\n")
        self.assert_blocked("task_identity")

    def test_oversize_changed_blob_fails_closed(self):
        large = "fixtures/large.txt"
        path = self.repo / large
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * (contract.MAX_SCANNED_FILE_BYTES + 1))
        self.write_packet(files=[DOC, large, TASK_PATH, BODY_PATH, MESSAGE_PATH])
        self.commit()
        self.assert_blocked("private_data_scan")

    def test_legacy_mode_still_requires_manifest_identity(self):
        self.assert_blocked("manifest mode requires an explicit task id", task_source="manifest")
        self.assert_blocked("missing or unsafe file", task_source="manifest", task=TASK)

    def test_workflow_uses_trusted_validator_with_attestation_only_write(self):
        workflow = (SOURCE / "templates/starter-workflows/speculoos-trusted-canary.yml").read_text()
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("startsWith(github.event.pull_request.head.ref, 'test/speculoos-shadow-')", workflow)
        self.assertIn("ref: ${{ github.sha }}", workflow)
        self.assertIn("path: trusted", workflow)
        self.assertIn("path: candidate", workflow)
        self.assertIn("python -I trusted/scripts/github/speculoos_per_pr_contract.py", workflow)
        self.assertIn("--trusted-repo trusted", workflow)
        self.assertIn("--task-source per-pr", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("attestations: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("checks: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("scripts/github/validate_pullfrog_workflow.sh", workflow)
        self.assertEqual(workflow, (SOURCE / ".github/workflows/speculoos-trusted-canary.yml").read_text())

    def test_workflow_materialization_is_read_from_separate_trusted_revision(self):
        trusted = Path(self.temp.name) / "trusted"
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(self.repo), str(trusted)], check=True)
        self.assertEqual(self.report(trusted_repo=str(trusted))["status"], "ok")
        manifest = trusted / "templates/repo-workflow-materialization-manifest.json"
        manifest.write_text('{"workflows": []}\n', encoding="utf-8")
        subprocess.run(["git", "-C", str(trusted), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(trusted), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(trusted), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(trusted), "commit", "-q", "-m", "change trusted manifest"], check=True)
        self.assert_blocked("workflow_materialization", trusted_repo=str(trusted))
        self.assertEqual(self.report()["status"], "ok")

    def test_trusted_main_can_validate_candidate_without_shadow_workflow_files(self):
        trusted = Path(self.temp.name) / "trusted"
        subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(self.repo), str(trusted)], check=True)
        packet = {name: (self.repo / name).read_text() for name in
                  (DOC, TASK_PATH, BODY_PATH, MESSAGE_PATH)}
        self.git("checkout", "-q", "dev")
        for name in ("templates/starter-workflows/speculoos-trusted-canary.yml",
                     ".github/workflows/speculoos-trusted-canary.yml",
                     "templates/repo-workflow-materialization-manifest.json",
                     "scripts/github/speculoos_per_pr_contract.py"):
            (self.repo / name).unlink()
        self.commit()
        self.base = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/dev", self.base)
        self.git("branch", "-D", HEAD_REF)
        self.git("checkout", "-q", "-b", HEAD_REF)
        for name, content in packet.items():
            self.write(name, content)
        self.commit()
        self.assertEqual(self.report(trusted_repo=str(trusted))["status"], "ok")
        self.assert_blocked("missing or unsafe file", trusted_repo=None)


if __name__ == "__main__":
    unittest.main()
