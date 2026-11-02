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
        self.assertTrue(receipt["evidence"]["checks_bound_to_head"])
        self.assertTrue(receipt["repository"]["protected_head_refs_valid"])
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

    def test_missing_wrong_type_or_malformed_claim_history_blocks(self):
        variants = [
            ("missing", None, "missing_claim_history"),
            ("wrong-type", "not-a-list", "invalid_claim_history"),
            ("malformed", ["not-a-canonical-claim-key"], "invalid_claim_history"),
            ("non-string", [7], "invalid_claim_history"),
        ]
        for name, value, blocker in variants:
            with self.subTest(name=name):
                scenario = self.load("ready.json")
                if name == "missing":
                    del scenario["run"]["prior_claim_keys"]
                else:
                    scenario["run"]["prior_claim_keys"] = value
                receipt = MODULE.evaluate_scenario(scenario)
                self.assertEqual(receipt["status"], "blocked")
                self.assertIn(blocker, receipt["blockers"])
                self.assertFalse(receipt["run"]["claim_history_valid"])

    def test_repository_case_is_normalized_for_claim_deduplication(self):
        scenario = self.load("ready.json")
        scenario["run"]["prior_claim_keys"] = [
            "FR-MEYER/AGENT-TOOLKIT:2222222222222222222222222222222222222222:1"
        ]
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("duplicate_claim", receipt["blockers"])
        self.assertTrue(receipt["run"]["claim_history_valid"])
        self.assertTrue(receipt["run"]["duplicate"])

    def test_case_variant_claim_history_duplicates_are_invalid(self):
        scenario = self.load("ready.json")
        scenario["run"]["prior_claim_keys"] = [
            "fr-meyer/agent-toolkit:3333333333333333333333333333333333333333:1",
            "FR-MEYER/AGENT-TOOLKIT:3333333333333333333333333333333333333333:1",
        ]
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("invalid_claim_history", receipt["blockers"])
        self.assertFalse(receipt["run"]["claim_history_valid"])

    def test_actor_overlap_blocks(self):
        receipt = MODULE.evaluate_scenario(self.load("actor-overlap.json"))
        self.assertEqual(receipt["status"], "blocked")
        self.assertIn("actor_identity_overlap", receipt["blockers"])
        self.assertFalse(receipt["actors"]["separated"])

    def test_malformed_or_whitespace_variant_actor_labels_block(self):
        for author_login, reviewer_login in [
            ("mergeguez[bot]", "mergeguez[bot] "),
            ("pullfrog[bot]", "bad_login"),
            ("mergeguez[bot]", "Mergeguez[bot]"),
        ]:
            with self.subTest(
                author_login=author_login,
                reviewer_login=reviewer_login,
            ):
                scenario = self.load("ready.json")
                scenario["actors"]["author_login"] = author_login
                scenario["actors"]["reviewer_login"] = reviewer_login
                receipt = MODULE.evaluate_scenario(scenario)
                self.assertEqual(receipt["status"], "blocked")
                self.assertFalse(receipt["actors"]["separated"])
                expected = (
                    "actor_identity_overlap"
                    if author_login.casefold() == reviewer_login.casefold()
                    else "invalid_actor_identity"
                )
                self.assertIn(expected, receipt["blockers"])

    def test_consecutive_hyphen_actor_labels_block(self):
        for author_login, reviewer_login in [
            ("pull--frog", "mergeguez"),
            ("pullfrog", "merge--guez"),
        ]:
            with self.subTest(
                author_login=author_login,
                reviewer_login=reviewer_login,
            ):
                scenario = self.load("ready.json")
                scenario["actors"]["author_login"] = author_login
                scenario["actors"]["reviewer_login"] = reviewer_login
                receipt = MODULE.evaluate_scenario(scenario)
                self.assertEqual(receipt["status"], "blocked")
                self.assertIn("invalid_actor_identity", receipt["blockers"])
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
            {
                "name": "dogfood-contract",
                "status": "success",
                "head_sha": scenario["repository"]["head_sha"],
            },
            {
                "name": "dogfood-contract",
                "status": "success",
                "head_sha": scenario["repository"]["head_sha"],
            },
        ]
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("protected_head_ref", receipt["blockers"])
        self.assertIn("invalid_required_check", receipt["blockers"])

    def test_nonstandard_protected_head_blocks(self):
        scenario = self.load("ready.json")
        scenario["repository"]["head_ref"] = "release"
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("protected_head_ref", receipt["blockers"])

    def test_missing_or_malformed_protected_head_set_blocks(self):
        variants = [
            ("missing", None),
            ("wrong-type", "dev,main"),
            ("empty", []),
            ("duplicate", ["dev", "dev"]),
            ("full-ref", ["refs/heads/dev"]),
            ("malformed", ["dev", "feature//invalid"]),
        ]
        for name, value in variants:
            with self.subTest(name=name):
                scenario = self.load("ready.json")
                if name == "missing":
                    del scenario["repository"]["protected_head_refs"]
                else:
                    scenario["repository"]["protected_head_refs"] = value
                receipt = MODULE.evaluate_scenario(scenario)
                self.assertIn("invalid_protected_head_refs", receipt["blockers"])

    def test_missing_authoritative_required_check_blocks(self):
        scenario = self.load("ready.json")
        scenario["evidence"]["required_checks"] = [
            {
                "name": "dogfood-contract",
                "status": "success",
                "head_sha": scenario["repository"]["head_sha"],
            },
        ]
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("missing_required_check", receipt["blockers"])
        self.assertEqual(receipt["evidence"]["missing_required_check_names"], ["unit-tests"])
        self.assertFalse(receipt["evidence"]["checks_green"])

    def test_unknown_check_blocks_even_when_required_checks_are_present(self):
        scenario = self.load("ready.json")
        scenario["evidence"]["required_checks"].append(
            {
                "name": "arbitrary-success",
                "status": "success",
                "head_sha": scenario["repository"]["head_sha"],
            }
        )
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("unexpected_required_check", receipt["blockers"])
        self.assertEqual(
            receipt["evidence"]["unexpected_required_check_names"],
            ["arbitrary-success"],
        )
        self.assertFalse(receipt["evidence"]["checks_green"])

    def test_stale_required_check_head_blocks(self):
        scenario = self.load("ready.json")
        scenario["evidence"]["required_checks"][0]["head_sha"] = "3" * 40
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("stale_required_check_head", receipt["blockers"])
        self.assertFalse(receipt["evidence"]["checks_bound_to_head"])
        self.assertFalse(receipt["evidence"]["checks_green"])

    def test_invalid_required_check_head_blocks(self):
        scenario = self.load("ready.json")
        scenario["evidence"]["required_checks"][0]["head_sha"] = "not-a-sha"
        receipt = MODULE.evaluate_scenario(scenario)
        self.assertIn("invalid_required_check_head_sha", receipt["blockers"])
        self.assertFalse(receipt["evidence"]["checks_bound_to_head"])
        self.assertFalse(receipt["evidence"]["checks_green"])

    def test_malformed_git_branch_refs_block(self):
        invalid_refs = [
            "feature/",
            "feature//name",
            ".hidden",
            "feature.lock",
            "feature/@{1}",
            "-dash",
        ]
        for head_ref in invalid_refs:
            with self.subTest(head_ref=head_ref):
                scenario = self.load("ready.json")
                scenario["repository"]["head_ref"] = head_ref
                receipt = MODULE.evaluate_scenario(scenario)
                self.assertIn("invalid_head_ref", receipt["blockers"])

    def test_malformed_repository_slugs_block(self):
        invalid_slugs = [
            "bad_owner/repository",
            "-bad/repository",
            "bad-/repository",
            "bad--owner/repository",
            ("a" * 40) + "/repository",
            "owner/" + ("r" * 101),
            "owner/..",
        ]
        for slug in invalid_slugs:
            with self.subTest(slug=slug):
                scenario = self.load("ready.json")
                scenario["repository"]["slug"] = slug
                scenario["run"]["claim_key"] = (
                    slug + ":2222222222222222222222222222222222222222:1"
                )
                receipt = MODULE.evaluate_scenario(scenario)
                self.assertIn("invalid_repository_slug", receipt["blockers"])

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
