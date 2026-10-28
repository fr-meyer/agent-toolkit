import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates/starter-workflows/speculoos.yml"
LIVE = REPO_ROOT / ".github/workflows/speculoos.yml"
MANIFEST = REPO_ROOT / "templates/repo-workflow-materialization-manifest.json"
PINNED_SPECULOOS_COMMIT = "8156bc20fc7563941c17514eb551e894ce29c89b"


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

    def test_speculoos_is_immutable_and_task_bound(self) -> None:
        self.assertIn(PINNED_SPECULOOS_COMMIT, self.template)
        self.assertIn("test \"$(speculoos --version)\" = 'speculoos 0.7.0'", self.template)
        self.assertIn("current task branch does not match pull-request head", self.template)
        self.assertIn("current task base does not match pull-request base", self.template)
        self.assertIn("speculoos validate", self.template)
        self.assertIn("speculoos publish-check", self.template)

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
