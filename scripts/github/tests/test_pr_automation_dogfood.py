import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "pr_automation_dogfood.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SPEC = importlib.util.spec_from_file_location("pr_automation_dogfood", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PrAutomationDogfoodTests(unittest.TestCase):
    def load(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_ready_fixture_allows_only_human_merge(self):
        receipt = MODULE.evaluate_scenario(self.load("ready.json"))
        self.assertEqual(receipt["status"], "ready_for_human_merge")
        self.assertEqual(receipt["blockers"], [])
        self.assertTrue(receipt["actors"]["separated"])
        self.assertTrue(receipt["evidence"]["reviewed_head_matches"])
        self.assertTrue(receipt["evidence"]["checks_green"])
        self.assertEqual(receipt["policy"]["merge_mode"], "human")
        self.assertFalse(receipt["policy"]["auto_merge"])

    def test_stale_review_blocks(self):
        receipt = MODULE.evaluate_scenario(self.load("stale-review.json"))
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("stale_review_head", receipt["blockers"])

    def test_duplicate_dispatch_blocks(self):
        receipt = MODULE.evaluate_scenario(self.load("duplicate-dispatch.json"))
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("duplicate_claim", receipt["blockers"])
        self.assertTrue(receipt["run"]["duplicate"])

    def test_actor_overlap_blocks(self):
        receipt = MODULE.evaluate_scenario(self.load("actor-overlap.json"))
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("actor_identity_overlap", receipt["blockers"])
        self.assertFalse(receipt["actors"]["separated"])

    def test_provider_or_secret_exposure_blocks(self):
        scenario = self.load("ready.json")
        scenario["policy"]["provider_calls"] = True
        scenario["policy"]["secrets_exposed"] = True
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("provider_call_forbidden", receipt["blockers"])
        self.assertIn("secret_exposure_forbidden", receipt["blockers"])

    def test_nonhuman_or_automatic_merge_blocks(self):
        scenario = self.load("ready.json")
        scenario["policy"]["merge_mode"] = "app"
        scenario["policy"]["auto_merge"] = True
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("nonhuman_merge_mode", receipt["blockers"])
        self.assertIn("auto_merge_forbidden", receipt["blockers"])

    def test_cycle_limit_and_unsafe_write_scope_block(self):
        scenario = self.load("ready.json")
        scenario["run"]["cycle"] = 3
        scenario["run"]["max_cycles"] = 2
        scenario["run"]["claim_key"] = "fr-meyer/agent-toolkit:" + ("2" * 40) + ":3"
        scenario["policy"]["write_scope"] = "repository"
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("cycle_limit_exceeded", receipt["blockers"])
        self.assertIn("unsafe_write_scope", receipt["blockers"])

    def test_protected_full_ref_and_invalid_check_identity_block(self):
        scenario = self.load("ready.json")
        scenario["repository"]["head_ref"] = "refs/heads/main"
        scenario["evidence"]["required_checks"] = [
            {"name": "dogfood-contract", "status": "success"},
            {"name": "dogfood-contract", "status": "success"},
        ]
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("protected_head_ref", receipt["blockers"])
        self.assertIn("invalid_required_check", receipt["blockers"])

    def test_receipt_digest_ignores_expectation_metadata(self):
        scenario = self.load("ready.json")
        first = MODULE.evaluate_scenario(scenario)["input_digest"]
        scenario["expected"] = {"status": "blocked", "blockers": ["not-real"]}
        second = MODULE.evaluate_scenario(scenario)["input_digest"]
        self.assertEqual(first, second)

    def test_receipt_does_not_copy_untrusted_notes(self):
        scenario = self.load("ready.json")
        scenario["notes"] = "sensitive arbitrary fixture text"
        rendered = json.dumps(MODULE.evaluate_scenario(scenario), sort_keys=True)
        self.assertNotIn("sensitive arbitrary fixture text", rendered)

    def test_cli_writes_deterministic_receipt_for_each_fixture(self):
        for fixture in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=fixture.name), tempfile.TemporaryDirectory() as temp_dir:
                out = Path(temp_dir) / "receipt.json"
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--scenario", str(fixture), "--out", str(out)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                receipt = json.loads(out.read_text(encoding="utf-8"))
                self.assertEqual(receipt["schema"], MODULE.RECEIPT_SCHEMA)
                self.assertIn(receipt["status"], {"blocked", "ready_for_human_merge"})


if __name__ == "__main__":
    unittest.main()
