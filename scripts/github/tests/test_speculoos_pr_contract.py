import argparse
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "speculoos_pr_contract.py"
SPEC = importlib.util.spec_from_file_location("speculoos_pr_contract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

TASK = "example-task"
HEAD_REF = "feat/example"
BASE_REF = "dev"


class SpeculoosPrContractUnitTests(unittest.TestCase):
    def test_top_level_scalar_is_strictly_top_level(self):
        text = "id: example-task\nnested:\n  id: wrong\n"
        self.assertEqual(MODULE._top_level_scalar(text, "id"), TASK)

    def test_nested_scalar_reads_delivery_mode(self):
        text = "delivery_policy:\n  mode: inherit_branch_policy\nnotes:\n  - kept\n"
        self.assertEqual(MODULE._nested_scalar(text, "delivery_policy", "mode"), "inherit_branch_policy")

    def test_changed_file_packet_parser(self):
        packet = "## Changed Files For Publish\n\n- `b.py`\n- `a.py`\n\n## Validation\n"
        self.assertEqual(MODULE._packet_changed_files(packet), ["a.py", "b.py"])

    def test_secret_patterns_detect_literal_tokens_but_not_secret_names(self):
        self.assertTrue(MODULE.SECRET_PATTERNS["github_token"].search("ghp_" + "A" * 30))
        self.assertFalse(any(pattern.search("PULLFROG_REMEDIATION_PUBLISH_TOKEN") for pattern in MODULE.SECRET_PATTERNS.values()))


class SpeculoosPrContractIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "base")
        self.base_sha = self.git("rev-parse", "HEAD").strip()
        self.git("branch", "-M", BASE_REF)
        self.git("update-ref", f"refs/remotes/origin/{BASE_REF}", self.base_sha)
        self.git("switch", "-qc", HEAD_REF)
        self._write_fixture()
        self.git("add", ".")
        self.git("commit", "-qm", "feature")
        self.head_sha = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def write(self, relative, content):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_fixture(self):
        changed = [
            ".github/workflows/speculoos.yml",
            ".speculoos/actors.json",
            ".speculoos/manifest.yaml",
            f".speculoos/tasks/{TASK}.yaml",
            "README.md",
            f"specs/{TASK}/commit-message.txt",
            f"specs/{TASK}/pr-body.md",
            "templates/repo-workflow-materialization-manifest.json",
            "templates/starter-workflows/speculoos.yml",
        ]
        workflow = "name: Speculoos\npermissions:\n  contents: read\n"
        self.write(".github/workflows/speculoos.yml", workflow)
        self.write("templates/starter-workflows/speculoos.yml", workflow)
        self.write(
            "templates/repo-workflow-materialization-manifest.json",
            json.dumps({"workflows": [{"source": "templates/starter-workflows/speculoos.yml", "target": ".github/workflows/speculoos.yml"}]}) + "\n",
        )
        self.write(".speculoos/manifest.yaml", f"current_task: {TASK}\n")
        self.write(
            f".speculoos/tasks/{TASK}.yaml",
            f"id: {TASK}\nbranch: {HEAD_REF}\nbase_branch: {BASE_REF}\ndelivery_policy:\n  mode: inherit_branch_policy\n",
        )
        self.write(
            ".speculoos/actors.json",
            json.dumps(
                {
                    "branch_policies": [
                        {
                            "name": "feature_to_non_stable",
                            "auto_merge": {
                                "enabled": True,
                                "forbidden_base_refs": ["main", "master"],
                                "required_evidence": sorted(MODULE.REQUIRED_EVIDENCE),
                            },
                        }
                    ],
                    "profiles": {
                        "github_actions_non_stable_auto_merge": {
                            "same_repository_required": True,
                            "force_push_allowed": False,
                        }
                    },
                }
            ) + "\n",
        )
        packet = (
            "## Summary\n\n"
            f"Task `{TASK}`. Feature PRs target `dev`. Release/promotion PRs target `main`.\n\n"
            "## Changed Files For Publish\n\n"
            + "\n".join(f"- `{path}`" for path in sorted(changed))
            + "\n\n## Documentation Impact\n\nUpdated `README.md`.\n"
        )
        self.write(f"specs/{TASK}/pr-body.md", packet)
        self.write(f"specs/{TASK}/commit-message.txt", f"fix: validate {TASK}\n\nFeature PRs target `dev`. Release/promotion PRs target `main`.\n")
        self.write("README.md", "feature\n")

    def args(self):
        return argparse.Namespace(
            repo=str(self.repo),
            repo_slug="fr-meyer/example",
            task=TASK,
            expected_head_ref=HEAD_REF,
            expected_head_sha=self.head_sha,
            expected_base_ref=BASE_REF,
            expected_base_sha=self.base_sha,
            output=None,
        )

    def test_valid_contract_passes(self):
        report = MODULE.validate(self.args())
        self.assertEqual(report["status"], "ok", report)
        self.assertEqual(report["blockers"], [])

    def test_head_mismatch_fails_closed(self):
        args = self.args()
        args.expected_head_sha = "f" * 40
        report = MODULE.validate(args)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item.startswith("exact_git_identity:") for item in report["blockers"]))

    def test_packet_drift_fails_closed(self):
        packet = self.repo / f"specs/{TASK}/pr-body.md"
        packet.write_text(packet.read_text(encoding="utf-8").replace("- `README.md`\n", ""), encoding="utf-8")
        self.git("add", str(packet.relative_to(self.repo)))
        self.git("commit", "-qm", "drift")
        self.head_sha = self.git("rev-parse", "HEAD").strip()
        report = MODULE.validate(self.args())
        self.assertIn("changed_files_match: packet=8 actual=9", report["blockers"])


if __name__ == "__main__":
    unittest.main()
