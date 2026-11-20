"""Trusted stdlib fixtures. Synthetic app/account IDs are NOT production identity."""
import copy
import importlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_pullfrog_review_contract as legacy


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = importlib.import_module("pullfrog_standalone_review")

    def fixture(self):
        request = dict(schema="pullfrog-standalone-request.v1",
            repository_slug=legacy.REPOSITORY, pr_number=95, request_id="fixture-request",
            initiator=dict(account_id=26621962, login="fr-meyer", type="User"),
            base_ref="dev", base_sha=legacy.BASE_SHA,
            head_ref="feat/pullfrog-write-capable-loop", head_sha=legacy.HEAD_SHA,
            task="Repair scoped issue", allowed_paths=["scripts/"],
            issued_at=100, expires_at=1000, policy_mode="standalone",
            budget=dict(max_attempts=2, max_seconds=300, max_cost_microusd=0))
        s = legacy.snapshot()
        s["binding"] = self.adapter.binding(request)
        s["trusted_pullfrog_identity"] = dict(app_id=123, account_id=456,
            login="pullfrog[bot]", type="Bot", app_slug="pullfrog")
        s["collection_complete"] = dict.fromkeys(
            ["reviews", "review_comments", "review_threads", "check_runs"], True)
        s["reviews"][0]["user"].update(id=456, type="Bot")
        for check in s["check_runs"]:
            check["app"]["id"] = 123
        s["review_threads"][0]["comments"]["nodes"][0]["author"].update(
            databaseId=456, type="Bot")
        return request, s

    def test_clean_and_replay_stability(self):
        r, s = self.fixture()
        before = copy.deepcopy(s)
        a = self.adapter.normalize(r, s)
        self.assertEqual(a["status"], "clean")
        self.assertEqual(a, self.adapter.normalize(r, json.loads(json.dumps(s))))
        self.assertEqual(s, before)
        self.assertNotIn("body", json.dumps(a))
        d = a.pop("evidence_digest")
        self.assertEqual(d, self.adapter.digest(a))

    def test_adversarial_mutations(self):
        cases = [
            lambda s: s["reviews"][0]["user"].update(id=457),
            lambda s: s["reviews"][0]["user"].update(id=True),
            lambda s: s["reviews"][0]["user"].update(type="User"),
            lambda s: s["check_runs"][0]["app"].update(id=124),
            lambda s: s["check_runs"][0]["app"].pop("id"),
            lambda s: s["reviews"][0].update(body="No new issues found"),
            lambda s: s["reviews"][0].update(commit_id="a"*40),
            lambda s: s["reviews"][0].update(state="DISMISSED"),
            lambda s: s["collection_complete"].update(review_threads=False),
            lambda s: s.pop("review_threads"),
            lambda s: s["review_threads"][0]["comments"]["nodes"][0]["author"].pop("databaseId"),
            lambda s: s["review_threads"][0].update(isResolved="true"),
            lambda s: s["observed_identity"].update(base_sha="a"*40),
            lambda s: s.pop("trusted_pullfrog_identity"),
            lambda s: s.update(reviews=[]),
            lambda s: s.update(review_comments=[None]),
        ]
        for i, mutate in enumerate(cases):
            with self.subTest(case=i):
                r, s = self.fixture()
                mutate(s)
                self.assertEqual(self.adapter.normalize(r, s)["status"], "incomplete")

    def test_unresolved_and_spoofed_thread(self):
        r, s = self.fixture()
        s["review_threads"][0]["isResolved"] = False
        self.assertNotEqual(self.adapter.normalize(r, s)["status"], "clean")
        s["review_threads"][0]["comments"]["nodes"][0]["author"]["databaseId"] = 999
        self.assertEqual(self.adapter.normalize(r, s)["status"], "incomplete")

    def test_binding_substitution(self):
        r, s = self.fixture()
        for key, value in [("head_sha", "a"*40), ("request_id", "other"),
                           ("repository_slug", "other/repo"), ("pr_number", 96)]:
            with self.subTest(key=key):
                altered = copy.deepcopy(s)
                altered["binding"][key] = value
                with self.assertRaises(importlib.import_module("pullfrog_standalone_contract").ContractError):
                    self.adapter.normalize(r, altered)

    def test_successor_keeps_original_request(self):
        r, s = self.fixture()
        successor = "a"*40
        s["binding"] = self.adapter.binding(r, head_sha=successor)
        for key in ("expected_identity", "observed_identity"):
            s[key]["head_sha"] = successor
        s["reviews"][0]["commit_id"] = successor
        for c in s["check_runs"]:
            c["head_sha"] = successor
        result = self.adapter.normalize(r, s, current_head_sha=successor)
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["binding"]["request_digest"], self.adapter.digest(r))
        self.assertEqual(r["head_sha"], legacy.HEAD_SHA)

    def test_inline_summary_and_event_redelivery_do_not_multiply_findings(self):
        r, s = self.fixture()
        s["reviews"][0]["body"] = "One issue " + legacy.MODULE.REVIEW_MARKER
        s["check_runs"][1]["conclusion"] = "failure"
        c = dict(id=701, pull_request_review_id=601, commit_id=legacy.HEAD_SHA,
                 path="scripts/example.py", line=12, body="Fix this",
                 user=dict(id=456, login="pullfrog[bot]", type="Bot"))
        s["review_comments"] = [c, copy.deepcopy(c)]
        out = self.adapter.normalize(r, s)
        self.assertEqual(out["status"], "findings")
        self.assertEqual(len(out["findings"]), 1)
        self.assertEqual(out, self.adapter.normalize(r, s))
        self.assertNotIn("action", out)


if __name__ == "__main__":
    unittest.main()
