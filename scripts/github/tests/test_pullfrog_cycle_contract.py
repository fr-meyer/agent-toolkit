import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_cycle_contract.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_cycle_contract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
NEXT_SHA = "3" * 40
OUTPUT_DIGEST = "a" * 64


def finding(summary="Reject stale exact-head evidence"):
    return {
        "id": "PF-1",
        "severity": "high",
        "path": "scripts/github/coordinator.py",
        "line": 42,
        "summary": summary,
    }


def base_state(with_findings=False):
    findings = [finding()] if with_findings else []
    approval_status = "failure" if with_findings else "success"
    return {
        "schema": MODULE.STATE_SCHEMA,
        "expected": {
            "slug": "fr-meyer/agent-toolkit",
            "pr_number": 94,
            "base_ref": "dev",
            "base_sha": BASE_SHA,
            "head_ref": "chore/pullfrog-full-automation",
            "head_sha": HEAD_SHA,
            "head_repository_slug": "fr-meyer/agent-toolkit",
        },
        "observed": {
            "slug": "fr-meyer/agent-toolkit",
            "pr_number": 94,
            "base_ref": "dev",
            "base_sha": BASE_SHA,
            "head_ref": "chore/pullfrog-full-automation",
            "head_sha": HEAD_SHA,
            "head_repository_slug": "fr-meyer/agent-toolkit",
        },
        "event": {
            "delivery_id": "delivery-1",
            "kind": "pullfrog_review_completed",
            "head_sha": HEAD_SHA,
        },
        "policy": {"max_cycles": 3},
        "cycle": {
            "number": 0,
            "claim_key": f"fr-meyer/agent-toolkit:94:{HEAD_SHA}:0",
        },
        "history": {
            "completed_claim_keys": [],
            "remediation_source_heads": [],
            "finding_set_digests": [],
            "output_digests": [],
        },
        "review": {
            "status": "success",
            "head_sha": HEAD_SHA,
            "review_id": "review-123",
            "output_digest": OUTPUT_DIGEST,
            "findings": findings,
        },
        "checks": [
            {"name": "pullfrog", "status": "success", "head_sha": HEAD_SHA},
            {"name": "pullfrog-approval", "status": approval_status, "head_sha": HEAD_SHA},
            {"name": "ci", "status": "success", "head_sha": HEAD_SHA},
            {"name": "speculoos", "status": "success", "head_sha": HEAD_SHA},
            {"name": "destination-guard", "status": "success", "head_sha": HEAD_SHA},
        ],
    }


def advance_to_cycle_one(state):
    prior_decision = MODULE.evaluate_state(state)
    state = copy.deepcopy(state)
    previous_head = state["observed"]["head_sha"]
    state["expected"]["head_sha"] = NEXT_SHA
    state["observed"]["head_sha"] = NEXT_SHA
    state["event"]["head_sha"] = NEXT_SHA
    state["event"]["delivery_id"] = "delivery-2"
    state["cycle"] = {
        "number": 1,
        "claim_key": f"fr-meyer/agent-toolkit:94:{NEXT_SHA}:1",
    }
    state["history"] = {
        "completed_claim_keys": [prior_decision["cycle"]["claim_key"]],
        "remediation_source_heads": [previous_head],
        "finding_set_digests": [prior_decision["review"]["finding_set_digest"]],
        "output_digests": [prior_decision["review"]["output_digest"]],
    }
    state["review"]["head_sha"] = NEXT_SHA
    state["review"]["review_id"] = "review-456"
    state["review"]["output_digest"] = "b" * 64
    for check in state["checks"]:
        check["head_sha"] = NEXT_SHA
    return state


class PullfrogCycleContractTests(unittest.TestCase):
    def test_clean_exact_head_completes(self):
        decision = MODULE.evaluate_state(base_state())
        self.assertEqual(decision["status"], "clean")
        self.assertEqual(decision["action"], "complete")
        self.assertEqual(decision["blockers"], [])
        self.assertEqual(decision["review"]["finding_count"], 0)

    def test_findings_authorize_only_next_bounded_remediation(self):
        decision = MODULE.evaluate_state(base_state(with_findings=True))
        self.assertEqual(decision["status"], "remediation_ready")
        self.assertEqual(decision["action"], "start_remediation")
        self.assertEqual(decision["cycle"]["next_number"], 1)
        self.assertEqual(decision["review"]["finding_count"], 1)
        rendered = json.dumps(decision, sort_keys=True)
        self.assertNotIn("Reject stale exact-head evidence", rendered)

    def test_every_observed_identity_drift_fails_closed(self):
        variants = {
            "repository_drift": ("slug", "fr-meyer/other"),
            "pr_drift": ("pr_number", 95),
            "base_ref_drift": ("base_ref", "main"),
            "base_sha_drift": ("base_sha", "4" * 40),
            "head_ref_drift": ("head_ref", "fix/other"),
            "head_sha_drift": ("head_sha", "4" * 40),
            "head_repository_drift": ("head_repository_slug", "fork/agent-toolkit"),
        }
        for blocker, (field, value) in variants.items():
            with self.subTest(blocker=blocker):
                state = base_state()
                state["observed"][field] = value
                decision = MODULE.evaluate_state(state)
                self.assertEqual(decision["status"], "stopped")
                self.assertIn(blocker, decision["blockers"])

    def test_base_and_head_cannot_be_the_same_commit(self):
        state = base_state()
        state["expected"]["base_sha"] = HEAD_SHA
        state["observed"]["base_sha"] = HEAD_SHA
        decision = MODULE.evaluate_state(state)
        self.assertIn("base_head_sha_match", decision["blockers"])

    def test_stale_event_review_and_check_heads_stop(self):
        state = base_state()
        state["event"]["head_sha"] = "4" * 40
        state["review"]["head_sha"] = "5" * 40
        state["checks"][0]["head_sha"] = "6" * 40
        decision = MODULE.evaluate_state(state)
        self.assertIn("stale_event_head", decision["blockers"])
        self.assertIn("stale_review_head", decision["blockers"])
        self.assertIn("stale_check_head", decision["blockers"])

    def test_missing_pending_failed_cancelled_and_timed_out_evidence_stop(self):
        for status in ["missing", "pending", "failure", "cancelled", "timed_out"]:
            with self.subTest(status=status):
                state = base_state()
                state["checks"][2]["status"] = status
                decision = MODULE.evaluate_state(state)
                self.assertIn(f"check_ci_{status}", decision["blockers"])
                self.assertEqual(decision["action"], "none")

    def test_missing_required_check_stops(self):
        state = base_state()
        state["checks"] = [item for item in state["checks"] if item["name"] != "speculoos"]
        decision = MODULE.evaluate_state(state)
        self.assertIn("missing_required_check", decision["blockers"])
        self.assertEqual(decision["evidence"]["missing_checks"], ["speculoos"])

    def test_approval_must_match_review_outcome(self):
        clean = base_state()
        clean["checks"][1]["status"] = "failure"
        self.assertIn(
            "inconsistent_pullfrog_approval",
            MODULE.evaluate_state(clean)["blockers"],
        )
        findings = base_state(with_findings=True)
        findings["checks"][1]["status"] = "success"
        self.assertIn(
            "inconsistent_pullfrog_approval",
            MODULE.evaluate_state(findings)["blockers"],
        )

    def test_duplicate_claim_is_idempotent_no_action(self):
        state = base_state(with_findings=True)
        state["history"]["completed_claim_keys"] = [state["cycle"]["claim_key"]]
        decision = MODULE.evaluate_state(state)
        self.assertEqual(decision["status"], "duplicate")
        self.assertEqual(decision["action"], "none")
        self.assertEqual(decision["blockers"], [])

    def test_new_head_requires_complete_cycle_history(self):
        state = advance_to_cycle_one(base_state(with_findings=True))
        state["history"]["output_digests"] = []
        decision = MODULE.evaluate_state(state)
        self.assertIn("incomplete_cycle_history", decision["blockers"])

    def test_duplicate_progress_digests_make_history_invalid(self):
        state = base_state(with_findings=True)
        state["expected"]["head_sha"] = "6" * 40
        state["observed"]["head_sha"] = "6" * 40
        state["event"]["head_sha"] = "6" * 40
        state["review"]["head_sha"] = "6" * 40
        state["review"]["output_digest"] = "7" * 64
        for check in state["checks"]:
            check["head_sha"] = "6" * 40
        state["cycle"] = {
            "number": 2,
            "claim_key": f"fr-meyer/agent-toolkit:94:{'6' * 40}:2",
        }
        state["history"] = {
            "completed_claim_keys": [
                f"fr-meyer/agent-toolkit:94:{'2' * 40}:0",
                f"fr-meyer/agent-toolkit:94:{'3' * 40}:1",
            ],
            "remediation_source_heads": ["2" * 40, "3" * 40],
            "finding_set_digests": ["4" * 64, "4" * 64],
            "output_digests": ["5" * 64, "5" * 64],
        }
        decision = MODULE.evaluate_state(state)
        self.assertIn("invalid_finding_digest_history", decision["blockers"])
        self.assertIn("invalid_output_digest_history", decision["blockers"])

    def test_unchanged_head_stops_no_progress(self):
        state = base_state(with_findings=True)
        state["cycle"] = {
            "number": 1,
            "claim_key": f"fr-meyer/agent-toolkit:94:{HEAD_SHA}:1",
        }
        prior = MODULE.evaluate_state(base_state(with_findings=True))
        state["history"] = {
            "completed_claim_keys": [prior["cycle"]["claim_key"]],
            "remediation_source_heads": [HEAD_SHA],
            "finding_set_digests": ["f" * 64],
            "output_digests": ["e" * 64],
        }
        decision = MODULE.evaluate_state(state)
        self.assertIn("unchanged_head", decision["blockers"])
        self.assertIn("reused_head", decision["blockers"])

    def test_repeated_findings_and_unchanged_output_stop(self):
        state = base_state(with_findings=True)
        state = advance_to_cycle_one(state)
        current = MODULE.evaluate_state(state)
        state["history"]["finding_set_digests"] = [current["review"]["finding_set_digest"]]
        state["history"]["output_digests"] = [state["review"]["output_digest"]]
        decision = MODULE.evaluate_state(state)
        self.assertIn("repeated_findings", decision["blockers"])
        self.assertIn("unchanged_output", decision["blockers"])

    def test_cycle_three_with_findings_stops(self):
        state = base_state(with_findings=True)
        state["expected"]["head_sha"] = "6" * 40
        state["observed"]["head_sha"] = "6" * 40
        state["event"]["head_sha"] = "6" * 40
        state["review"]["head_sha"] = "6" * 40
        for check in state["checks"]:
            check["head_sha"] = "6" * 40
        state["cycle"] = {
            "number": 3,
            "claim_key": f"fr-meyer/agent-toolkit:94:{'6' * 40}:3",
        }
        state["history"] = {
            "completed_claim_keys": [
                f"fr-meyer/agent-toolkit:94:{digit * 40}:{index}"
                for index, digit in enumerate(["2", "3", "4"])
            ],
            "remediation_source_heads": ["2" * 40, "3" * 40, "4" * 40],
            "finding_set_digests": ["1" * 64, "2" * 64, "3" * 64],
            "output_digests": ["4" * 64, "5" * 64, "6" * 64],
        }
        state["review"]["output_digest"] = "7" * 64
        decision = MODULE.evaluate_state(state)
        self.assertEqual(decision["status"], "stopped")
        self.assertIn("cycle_limit_exhausted", decision["blockers"])

    def test_review_failure_states_stop(self):
        for status in ["missing", "pending", "failure", "cancelled", "timed_out"]:
            with self.subTest(status=status):
                state = base_state()
                state["review"]["status"] = status
                decision = MODULE.evaluate_state(state)
                self.assertIn(f"review_{status}", decision["blockers"])

    def test_malformed_finding_and_path_stop(self):
        state = base_state(with_findings=True)
        state["review"]["findings"][0]["path"] = "../secret"
        decision = MODULE.evaluate_state(state)
        self.assertIn("invalid_finding", decision["blockers"])

    def test_max_cycles_cannot_exceed_three(self):
        state = base_state(with_findings=True)
        state["policy"]["max_cycles"] = 4
        decision = MODULE.evaluate_state(state)
        self.assertIn("invalid_max_cycles", decision["blockers"])

    def test_input_notes_are_not_copied_to_receipt(self):
        state = base_state()
        state["notes"] = "untrusted private note"
        rendered = json.dumps(MODULE.evaluate_state(state), sort_keys=True)
        self.assertNotIn("untrusted private note", rendered)

    def test_cli_is_deterministic_and_fail_on_stopped_is_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "state.json"
            first = root / "first.json"
            second = root / "second.json"
            state_path.write_text(json.dumps(base_state()), encoding="utf-8")
            for out in (first, second):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--state", str(state_path), "--out", str(out)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            stopped = base_state()
            stopped["event"]["head_sha"] = "9" * 40
            state_path.write_text(json.dumps(stopped), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--state",
                    str(state_path),
                    "--out",
                    str(first),
                    "--fail-on-stopped",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
