import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates/starter-workflows/pullfrog.yml"
LIVE = REPO_ROOT / ".github/workflows/pullfrog.yml"
VALIDATOR = REPO_ROOT / "scripts/github/validate_pullfrog_workflow.sh"
EXPECTED_HEADER = (
    "# Managed by templates/repo-workflow-materialization-manifest.json.\n"
    "# Edit templates/starter-workflows/pullfrog.yml, then rematerialize the live workflow.\n"
)
SECRET_EXPRESSION = re.compile(
    r"\$\{\{\s*secrets\s*(?:\.|\[)",
    flags=re.IGNORECASE,
)
ENV_MAPPING = re.compile(r"(?m)^[ \t]*env[ \t]*:")


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


class PullfrogWorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")
        self.live = LIVE.read_text(encoding="utf-8")

    def test_materialized_workflow_matches_the_canonical_template(self):
        self.assertEqual(self.live, self.template)
        self.assertTrue(self.template.startswith(EXPECTED_HEADER))

    def test_trigger_is_manual_dispatch_only(self):
        trigger = top_level_section(self.template, "on")
        keys = re.findall(r"^  ([a-zA-Z0-9_-]+):", trigger, flags=re.MULTILINE)
        self.assertEqual(keys, ["workflow_dispatch"])

    def test_permissions_timeouts_and_checkout_are_bounded(self):
        self.assertEqual(top_level_section(self.template, "permissions"), "  contents: read\n")
        job_permissions = re.search(
            r"(?m)^    permissions:\n(?P<body>(?:      [^\n]+\n)+)", self.template
        )
        self.assertIsNotNone(job_permissions)
        self.assertEqual(
            job_permissions.group("body"),
            "      id-token: write\n      contents: read\n",
        )
        self.assertIn("    timeout-minutes: 20\n", self.template)
        self.assertIn("          timeout: 15m\n", self.template)
        self.assertIn("          persist-credentials: false\n", self.template)

    def test_third_party_actions_are_exactly_pinned(self):
        uses = re.findall(r"^\s+uses:\s+([^\s#]+)", self.template, flags=re.MULTILINE)
        self.assertEqual(
            uses,
            [
                "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
                "pullfrog/pullfrog@25a837a2b078177c3acdce790506d1fd1acedd82",
            ],
        )
        for use in uses:
            self.assertRegex(use, r"@[0-9a-f]{40}$")

    def test_actionlint_release_asset_is_checksum_pinned(self):
        validator = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn('actionlint_version="1.7.12"', validator)
        self.assertIn(
            'archive_name="actionlint_${actionlint_version}_linux_amd64.tar.gz"',
            validator,
        )
        self.assertIn(
            'actionlint_sha256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"',
            validator,
        )
        self.assertIn("sha256sum --check --status", validator)

    def test_pullfrog_inputs_keep_publication_disabled(self):
        pullfrog_inputs = re.search(
            r"(?m)^        uses: pullfrog/pullfrog@[0-9a-f]{40}[^\n]*\n"
            r"        with:\n(?P<body>(?:          [^\n]+\n)+)",
            self.template,
        )
        self.assertIsNotNone(pullfrog_inputs)
        pairs = re.findall(
            r"(?m)^          ([a-z_]+): (.+)$", pullfrog_inputs.group("body")
        )
        self.assertEqual(
            pairs,
            [
                ("prompt", "${{ inputs.prompt }}"),
                ("timeout", "15m"),
                ("push", "disabled"),
                ("shell", "restricted"),
                ("progress_comments", "disabled"),
            ],
        )
        self.assertIsNone(SECRET_EXPRESSION.search(self.template))
        self.assertIsNone(ENV_MAPPING.search(self.template))
        self.assertNotIn("push: restricted", self.template)

    def test_secret_mapping_guard_rejects_whitespace_and_inline_forms(self):
        variants = [
            'env: {KEY: "${{secrets.KEY}}"}',
            'env : {KEY: "${{  SeCrEtS . KEY  }}"}',
            'env:\n  KEY: "${{ secrets[\'KEY\'] }}"',
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertIsNotNone(ENV_MAPPING.search(variant))
                self.assertIsNotNone(SECRET_EXPRESSION.search(variant))


if __name__ == "__main__":
    unittest.main()
