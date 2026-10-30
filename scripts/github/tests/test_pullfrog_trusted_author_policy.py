import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "pullfrog_trusted_author_policy.py"
SPEC = importlib.util.spec_from_file_location("pullfrog_trusted_author_policy", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

REPOSITORY = "fr-meyer/agent-toolkit"
EXPECTED_POLICY_DIGEST = "657eaab8a92d2517165f59a2746770ccfac70c340235040bf45aaca7b577b41f"
BASE_SHA = "1" * 40
HEAD_SHA = "2" * 40
NEXT_SHA = "3" * 40


def policy():
    return {
        "schema": MODULE.POLICY_SCHEMA,
        "repository_slug": REPOSITORY,
        "trusted_authors": [
            {"account_id": 26621962, "login": "fr-meyer", "type": "User"},
            {
                "account_id": 285669409,
                "login": "mergeguez[bot]",
                "type": "Bot",
            },
            {
                "account_id": 325213916,
                "login": "le-commis[bot]",
                "type": "Bot",
            },
        ],
    }


def live_author(
    account_id=26621962,
    login="fr-meyer",
    account_type="User",
    node_id="MDQ6VXNlcjI2NjIxOTYy",
):
    return {
        "id": account_id,
        "login": login,
        "type": account_type,
        "node_id": node_id,
        "avatar_url": "https://example.invalid/untrusted-extra-field",
    }


def pull_request(
    *,
    author=None,
    head_repository=REPOSITORY,
    base_repository=REPOSITORY,
    base_ref="dev",
    base_sha=BASE_SHA,
    head_sha=HEAD_SHA,
    draft=False,
    state="open",
):
    return {
        "number": 95,
        "state": state,
        "draft": draft,
        "user": copy.deepcopy(author or live_author()),
        "base": {
            "ref": base_ref,
            "sha": base_sha,
            "repo": {"full_name": base_repository},
        },
        "head": {
            "ref": "feat/pullfrog-write-capable-loop",
            "sha": head_sha,
            "repo": {"full_name": head_repository},
        },
    }


class PullfrogTrustedAuthorPolicyTests(unittest.TestCase):
    def test_repository_artifact_is_canonical_and_authorizes_all_initial_identities(self):
        loaded = MODULE.load_policy(REPOSITORY)
        self.assertEqual(loaded, MODULE.parse_policy(policy(), REPOSITORY))
        self.assertEqual(MODULE.policy_digest(loaded), EXPECTED_POLICY_DIGEST)
        for author in [
            live_author(),
            live_author(285669409, "mergeguez[bot]", "Bot", "BOT_node_1"),
            live_author(325213916, "le-commis[bot]", "Bot", "BOT_node_2"),
        ]:
            with self.subTest(login=author["login"]):
                receipt = MODULE.evaluate_author(loaded, author)
                self.assertTrue(receipt["authorized"])
                self.assertEqual(receipt["reason"], "trusted_author")
                self.assertEqual(
                    receipt["policy"]["digest"], MODULE.policy_digest(loaded)
                )

    def test_numeric_account_id_is_primary_and_login_only_never_authorizes(self):
        receipt = MODULE.evaluate_author(
            policy(), live_author(999999999, "fr-meyer", "User")
        )
        self.assertFalse(receipt["authorized"])
        self.assertEqual(receipt["reason"], "untrusted_account_id")
        with self.assertRaisesRegex(
            MODULE.TrustedAuthorPolicyError, "invalid_live_author_id"
        ):
            MODULE.evaluate_author(
                policy(), {"login": "fr-meyer", "type": "User"}
            )

    def test_casefolded_login_matches_but_rename_and_type_drift_stop(self):
        matched = MODULE.evaluate_author(
            policy(), live_author(login="Fr-Meyer")
        )
        self.assertTrue(matched["authorized"])
        self.assertEqual(matched["author"]["login"], "fr-meyer")

        renamed = MODULE.evaluate_author(
            policy(), live_author(login="fr-meyer-renamed")
        )
        self.assertFalse(renamed["authorized"])
        self.assertEqual(renamed["reason"], "author_login_drift")

        drifted = MODULE.evaluate_author(
            policy(), live_author(285669409, "mergeguez[bot]", "User")
        )
        self.assertFalse(drifted["authorized"])
        self.assertEqual(drifted["reason"], "author_type_drift")

    def test_node_id_is_diagnostic_only_and_excluded_from_digest(self):
        first = MODULE.evaluate_author(policy(), live_author(node_id="NODE_one"))
        second = MODULE.evaluate_author(policy(), live_author(node_id="NODE_two"))
        self.assertTrue(first["authorized"])
        self.assertTrue(second["authorized"])
        self.assertNotEqual(first["author"]["node_id"], second["author"]["node_id"])
        self.assertEqual(first["policy"]["digest"], second["policy"]["digest"])

    def test_policy_digest_is_stable_under_input_order(self):
        reordered = policy()
        reordered["trusted_authors"].reverse()
        self.assertEqual(
            MODULE.policy_digest(policy()), MODULE.policy_digest(reordered)
        )

    def test_policy_is_repository_bound(self):
        with self.assertRaisesRegex(
            MODULE.TrustedAuthorPolicyError, "policy_repository_mismatch"
        ):
            MODULE.parse_policy(policy(), "fr-meyer/other")

    def test_unknown_or_missing_policy_fields_fail_closed(self):
        variants = []
        changed = policy()
        changed["extra"] = True
        variants.append(changed)
        changed = policy()
        del changed["schema"]
        variants.append(changed)
        changed = policy()
        changed["trusted_authors"][0]["node_id"] = "diagnostic-not-policy"
        variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed):
                with self.assertRaises(MODULE.TrustedAuthorPolicyError):
                    MODULE.parse_policy(changed)

    def test_duplicate_ids_and_logins_fail_closed(self):
        duplicate_id = policy()
        duplicate_id["trusted_authors"][1]["account_id"] = 26621962
        with self.assertRaisesRegex(
            MODULE.TrustedAuthorPolicyError, "duplicate_policy_author_id"
        ):
            MODULE.parse_policy(duplicate_id)

        duplicate_login = policy()
        duplicate_login["trusted_authors"][1] = {
            "account_id": 42,
            "login": "fr-meyer",
            "type": "User",
        }
        with self.assertRaisesRegex(
            MODULE.TrustedAuthorPolicyError, "duplicate_policy_author_login"
        ):
            MODULE.parse_policy(duplicate_login)

    def test_invalid_ids_logins_and_types_fail_closed(self):
        variants = []
        for invalid_id in (None, True, 0, -1, "26621962"):
            changed = policy()
            changed["trusted_authors"][0]["account_id"] = invalid_id
            variants.append(changed)
        for login in ("Fr-Meyer", "-franck", "franck-", "fr--meyer"):
            changed = policy()
            changed["trusted_authors"][0]["login"] = login
            variants.append(changed)
        changed = policy()
        changed["trusted_authors"][0]["type"] = "Organization"
        variants.append(changed)
        changed = policy()
        changed["trusted_authors"][0]["type"] = "Bot"
        variants.append(changed)
        changed = policy()
        changed["trusted_authors"][1]["type"] = "User"
        variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed):
                with self.assertRaises(MODULE.TrustedAuthorPolicyError):
                    MODULE.parse_policy(changed)

    def test_duplicate_json_keys_fail_closed(self):
        raw = (
            '{"schema":"pullfrog-trusted-author-policy.v1",'
            '"schema":"pullfrog-trusted-author-policy.v1",'
            '"repository_slug":"fr-meyer/agent-toolkit",'
            '"trusted_authors":[]}'
        )
        with self.assertRaisesRegex(
            MODULE.TrustedAuthorPolicyError, "duplicate_policy_key"
        ):
            MODULE.parse_policy_json(raw)

    def test_invalid_json_encoding_size_and_empty_policy_fail_closed(self):
        for raw in (b"", b"\xff", b"{", b"x" * (MODULE.MAX_POLICY_BYTES + 1)):
            with self.subTest(length=len(raw)):
                with self.assertRaises(MODULE.TrustedAuthorPolicyError):
                    MODULE.parse_policy_json(raw)
        empty = policy()
        empty["trusted_authors"] = []
        with self.assertRaisesRegex(
            MODULE.TrustedAuthorPolicyError, "invalid_policy_authors"
        ):
            MODULE.parse_policy(empty)

    def test_loader_rejects_symlinked_policy_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target.json"
            target.write_text(json.dumps(policy()), encoding="utf-8")
            link = root / "policy.json"
            link.symlink_to(target)
            with mock.patch.object(MODULE, "POLICY_PATH", link):
                with self.assertRaisesRegex(
                    MODULE.TrustedAuthorPolicyError, "invalid_policy_file"
                ):
                    MODULE.load_policy(REPOSITORY)

    def test_loader_has_no_path_or_environment_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            attacker = Path(temp_dir) / "policy.json"
            changed = policy()
            changed["trusted_authors"] = [
                {"account_id": 1, "login": "attacker", "type": "User"}
            ]
            attacker.write_text(json.dumps(changed), encoding="utf-8")
            with mock.patch.dict(
                "os.environ",
                {
                    "PULLFROG_TRUSTED_AUTHOR_POLICY": str(attacker),
                    "POLICY_PATH": str(attacker),
                },
                clear=False,
            ):
                loaded = MODULE.load_policy(REPOSITORY)
        self.assertEqual(loaded, MODULE.parse_policy(policy(), REPOSITORY))

    def test_external_contributor_and_fork_are_review_only(self):
        external = live_author(444444444, "external-user", "User", "NODE_external")
        pr = pull_request(author=external, head_repository="external/agent-toolkit")
        receipt = MODULE.evaluate_pull_request_authority(
            policy(), REPOSITORY, pr, copy.deepcopy(pr)
        )
        self.assertTrue(receipt["review_eligible"])
        self.assertFalse(receipt["same_repository"])
        self.assertFalse(receipt["trusted_author"])
        self.assertFalse(receipt["mutation_authorized"])
        self.assertEqual(receipt["blockers"], [])

    def test_untrusted_same_repository_author_is_review_only(self):
        pr = pull_request(
            author=live_author(444444444, "untrusted-user", "User", "NODE_untrusted")
        )
        receipt = MODULE.evaluate_pull_request_authority(
            policy(), REPOSITORY, pr, copy.deepcopy(pr)
        )
        self.assertTrue(receipt["review_eligible"])
        self.assertTrue(receipt["same_repository"])
        self.assertFalse(receipt["trusted_author"])
        self.assertFalse(receipt["mutation_authorized"])
        self.assertEqual(
            receipt["author_decision"]["reason"], "untrusted_account_id"
        )

    def test_trusted_human_and_custom_app_bots_are_mutation_authorized(self):
        authors = (
            live_author(),
            live_author(285669409, "mergeguez[bot]", "Bot", "BOT_mergeguez"),
            live_author(325213916, "le-commis[bot]", "Bot", "BOT_le_commis"),
        )
        for author in authors:
            with self.subTest(login=author["login"]):
                pr = pull_request(author=author)
                receipt = MODULE.evaluate_pull_request_authority(
                    policy(), REPOSITORY, pr, copy.deepcopy(pr)
                )
                self.assertTrue(receipt["review_eligible"])
                self.assertTrue(receipt["same_repository"])
                self.assertTrue(receipt["trusted_author"])
                self.assertTrue(receipt["mutation_authorized"])

    def test_malformed_author_and_pull_request_identity_fail_closed(self):
        variants = []
        malformed = pull_request()
        del malformed["user"]["id"]
        variants.append(malformed)
        malformed = pull_request()
        malformed["base"]["repo"]["full_name"] = ""
        variants.append(malformed)
        malformed = pull_request()
        malformed["head"]["sha"] = "not-a-sha"
        variants.append(malformed)
        for pr in variants:
            with self.subTest(pr=pr):
                receipt = MODULE.evaluate_pull_request_authority(
                    policy(), REPOSITORY, pr, copy.deepcopy(pr)
                )
                self.assertFalse(receipt["review_eligible"])
                self.assertFalse(receipt["mutation_authorized"])
                self.assertTrue(receipt["blockers"])

    def test_drafts_closed_prs_and_non_governed_targets_are_not_review_eligible(self):
        variants = (
            pull_request(draft=True),
            pull_request(state="closed"),
            pull_request(base_repository="external/agent-toolkit"),
            pull_request(base_ref="staging"),
        )
        for pr in variants:
            with self.subTest(pr=pr):
                receipt = MODULE.evaluate_pull_request_authority(
                    policy(), REPOSITORY, pr, copy.deepcopy(pr)
                )
                self.assertFalse(receipt["review_eligible"])
                self.assertFalse(receipt["mutation_authorized"])

    def test_retargeting_and_exact_head_or_author_drift_fail_closed(self):
        mutations = (
            ("base_ref", lambda pr: pr["base"].__setitem__("ref", "main")),
            ("base_sha", lambda pr: pr["base"].__setitem__("sha", NEXT_SHA)),
            ("head_sha", lambda pr: pr["head"].__setitem__("sha", NEXT_SHA)),
            (
                "author",
                lambda pr: pr.__setitem__(
                    "user", live_author(444444444, "external-user", "User")
                ),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                expected = pull_request()
                observed = copy.deepcopy(expected)
                mutate(observed)
                receipt = MODULE.evaluate_pull_request_authority(
                    policy(), REPOSITORY, expected, observed
                )
                self.assertFalse(receipt["review_eligible"])
                self.assertFalse(receipt["mutation_authorized"])
                self.assertTrue(
                    any(blocker.endswith("_drift") for blocker in receipt["blockers"])
                )

    def test_pull_request_node_id_drift_is_diagnostic_only(self):
        expected = pull_request()
        observed = copy.deepcopy(expected)
        observed["user"]["node_id"] = "NODE_diagnostic_change"
        receipt = MODULE.evaluate_pull_request_authority(
            policy(), REPOSITORY, expected, observed
        )
        self.assertTrue(receipt["review_eligible"])
        self.assertTrue(receipt["trusted_author"])
        self.assertTrue(receipt["mutation_authorized"])
        self.assertEqual(receipt["blockers"], [])

    def test_pull_request_author_extraction_requires_complete_identity(self):
        pr = {"user": live_author()}
        self.assertEqual(
            MODULE.author_from_pull_request(pr),
            MODULE.normalize_live_author(pr["user"]),
        )
        for user in ({}, None, {"id": 26621962, "login": "fr-meyer"}):
            with self.subTest(user=user):
                with self.assertRaises(MODULE.TrustedAuthorPolicyError):
                    MODULE.author_from_pull_request({"user": user})


if __name__ == "__main__":
    unittest.main()
