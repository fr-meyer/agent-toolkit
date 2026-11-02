import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates/starter-workflows/speculoos.yml"
LIVE = REPO_ROOT / ".github/workflows/speculoos.yml"
MANIFEST = REPO_ROOT / "templates/repo-workflow-materialization-manifest.json"

class PullfrogSpeculoosWorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = TEMPLATE.read_text(encoding="utf-8")

    def test_materialized_workflow_is_registered_and_identical(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn(
            {
                "source": "templates/starter-workflows/speculoos.yml",
                "target": ".github/workflows/speculoos.yml",
            },
            manifest["workflows"],
        )
        self.assertEqual(self.template, LIVE.read_text(encoding="utf-8"))

    def test_exact_check_name_and_non_stable_pr_trigger(self) -> None:
        self.assertIn("name: Speculoos\n", self.template)
        self.assertIn("  pull_request:\n", self.template)
        self.assertIn("      - '**'\n", self.template)
        self.assertIn("      - '!main'\n", self.template)
        self.assertIn("      - '!master'\n", self.template)
        self.assertIn("  speculoos:\n    name: speculoos\n", self.template)

    def test_read_only_exact_head_checkout(self) -> None:
        self.assertIn("permissions:\n  contents: read\n", self.template)
        self.assertNotIn("contents: write", self.template)
        self.assertNotIn("pull-requests: write", self.template)
        self.assertNotIn("id-token: write", self.template)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", self.template)
        self.assertIn("fetch-depth: 0", self.template)
        self.assertIn("persist-credentials: false", self.template)
        self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"', self.template)

    def test_speculoos_contract_is_zero_secret_and_task_bound(self) -> None:
        self.assertNotIn("git+https://github.com/fr-meyer/speculoos", self.template)
        self.assertIn("scripts/github/speculoos_pr_contract.py", self.template)
        self.assertIn("--task \"$task_id\"", self.template)
        self.assertIn("--expected-head-ref \"$EXPECTED_HEAD_REF\"", self.template)
        self.assertIn("--expected-head-sha \"$EXPECTED_HEAD_SHA\"", self.template)
        self.assertIn("--expected-base-ref \"$EXPECTED_BASE_REF\"", self.template)
        self.assertIn("--expected-base-sha \"$EXPECTED_BASE_SHA\"", self.template)
        self.assertIn("scripts/github/validate_pullfrog_workflow.sh", self.template)
        self.assertIn("mkdir -p artifacts/speculoos", self.template)
        self.assertIn("if-no-files-found: warn", self.template)

    def test_python_entrypoints_are_import_isolated(self) -> None:
        self.assertIn("task_id=\"$(python -I - <<'PY'", self.template)
        self.assertIn(
            "python -I scripts/github/speculoos_pr_contract.py",
            self.template,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scripts = root / "scripts/github"
            scripts.mkdir(parents=True)
            validator = scripts / "speculoos_pr_contract.py"
            validator.write_text(
                (REPO_ROOT / "scripts/github/speculoos_pr_contract.py").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            (scripts / "argparse.py").write_text(
                "raise SystemExit(87)\n", encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, "-I", str(validator), "--help"],
                cwd=root,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_actions_are_immutable_and_evidence_is_retained(self) -> None:
        self.assertIn(
            "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
            self.template,
        )
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            self.template,
        )
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            self.template,
        )
        self.assertIn("retention-days: 90", self.template)


if __name__ == "__main__":
    unittest.main()
