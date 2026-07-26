#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repository_similarity_preflight.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "openclaw-continuation-106704.json"


def load_module():
    spec = importlib.util.spec_from_file_location("repository_similarity_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source(kind: str, items: list[dict] | None = None, *, status: str = "complete") -> dict:
    value = {"kind": kind, "status": status}
    if status == "not_applicable":
        value["reason"] = "The source does not apply to this fixture."
    else:
        value["items"] = items or []
    return value


def base_payload() -> dict:
    return {
        "schema_version": "repository-similarity-preflight/v1",
        "repository": {
            "host": "github.com",
            "owner": "example",
            "name": "project",
            "visibility": "public",
            "revision": "base-revision",
            "branch": "planned/change",
        },
        "intent": {
            "title": "Add repository similarity preflight",
            "summary": "Check existing repository work before opening a new issue or pull request.",
            "target": "issue",
            "terms": ["duplicate", "canonical", "preflight", "issue"],
            "behavior_names": ["similarity screen"],
        },
        "search": {
            "auth": {"status": "anonymous"},
            "queries": ["repository similarity preflight", "duplicate canonical issue"],
            "sources": [
                source("issues"),
                source("discussions", status="not_applicable"),
                source("pull_requests"),
                source("releases"),
                source("docs"),
                source("code"),
                source("tests"),
            ],
        },
    }


class RepositorySimilarityPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_exact_duplicate_blocks_new_issue_and_routes_canonical_item(self) -> None:
        payload = base_payload()
        payload["search"]["sources"][0]["items"] = [
            {
                "number": 7,
                "url": "https://github.com/example/project/issues/7",
                "state": "open",
                "title": "Add repository similarity preflight",
                "relationship": "duplicate",
                "reason": "Same requested preflight behavior.",
            }
        ]
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "duplicate")
        self.assertEqual(report["matches"][0]["number"], 7)
        self.assertIn("canonical", report["reason"])

    def test_synonym_overlap_is_related(self) -> None:
        payload = base_payload()
        payload["search"]["sources"][0]["items"] = [
            {
                "number": 8,
                "url": "https://github.com/example/project/issues/8",
                "state": "open",
                "title": "Prevent repeated issue creation with canonical routing",
                "summary": "A duplicate check should run before a new request.",
            }
        ]
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "related")
        self.assertEqual(report["matches"][0]["match_type"], "synonym_or_term_overlap")

    def test_closed_superseded_match_remains_related(self) -> None:
        payload = base_payload()
        payload["search"]["sources"][0]["items"] = [
            {
                "number": 9,
                "url": "https://github.com/example/project/issues/9",
                "state": "closed",
                "title": "Old duplicate-preflight proposal",
                "relationship": "superseded",
                "reason": "Superseded by the canonical implementation thread.",
            }
        ]
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "related")

    def test_no_match_passes_with_complete_search_coverage(self) -> None:
        report = self.module.build_report(base_payload())
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["matches"], [])

    def test_auth_failure_blocks_instead_of_claiming_no_match(self) -> None:
        payload = base_payload()
        payload["search"]["auth"] = {"status": "unavailable"}
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item["code"] == "search_auth_unavailable" for item in report["blockers"]))

    def test_private_repo_requires_approved_authenticated_lane(self) -> None:
        payload = base_payload()
        payload["repository"]["visibility"] = "private"
        payload["search"]["auth"] = {"status": "anonymous"}
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "blocked")

    def test_unsafe_public_evidence_is_redacted_and_blocks(self) -> None:
        payload = base_payload()
        synthetic_email = "synthetic" + "@example.invalid"
        synthetic_path = "/" + "home/synthetic/private.txt"
        payload["search"]["queries"] = [f"contact {synthetic_email} using {synthetic_path}"]
        payload["search"]["sources"][0]["items"] = [
            {
                "number": 10,
                "url": "https://github.com/example/project/issues/10?token=secret-value",
                "state": "open",
                "title": "Unsafe evidence",
                "relationship": "unrelated",
                "reason": "secret=do-not-echo",
            }
        ]
        report = self.module.build_report(payload)
        encoded = json.dumps(report)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(report["redaction"]["findings"])
        self.assertNotIn(synthetic_email, encoded)
        self.assertNotIn(synthetic_path, encoded)
        self.assertNotIn("do-not-echo", encoded)
        self.assertNotIn("secret-value", encoded)

    def test_related_match_without_route_blocks(self) -> None:
        payload = base_payload()
        payload["search"]["sources"][0]["items"] = [
            {
                "state": "open",
                "title": "Same preflight request",
                "relationship": "directly_related",
                "reason": "No stable URL was recorded.",
            }
        ]
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item["code"] == "canonical_route_missing" for item in report["blockers"]))

    def test_external_write_requires_scoped_approval_after_clean_pass(self) -> None:
        payload = base_payload()
        blocked = self.module.build_report(payload, external_write=True)
        self.assertEqual(blocked["status"], "blocked")
        self.assertFalse(blocked["external_write"]["allowed"])

        payload["external_write"] = {
            "approval": {"authorized": True, "scope": "create the approved pull request"}
        }
        allowed = self.module.build_report(payload, external_write=True)
        self.assertEqual(allowed["status"], "pass")
        self.assertTrue(allowed["external_write"]["allowed"])

    def test_not_applicable_requires_reason(self) -> None:
        payload = base_payload()
        payload["intent"]["not_applicable"] = True
        payload["intent"]["not_applicable_reason"] = "No repository issue, PR, or code change is involved."
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "not-applicable")

    def test_not_applicable_cannot_authorize_external_write(self) -> None:
        payload = base_payload()
        payload["intent"]["not_applicable"] = True
        payload["intent"]["not_applicable_reason"] = "No repository issue, PR, or code change is involved."
        payload["external_write"] = {"approval": {"authorized": True, "scope": "create a pull request"}}
        report = self.module.build_report(payload, external_write=True)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["external_write"]["allowed"])
        self.assertTrue(any(item["code"] == "external_write_not_allowed" for item in report["blockers"]))

    def test_url_redaction_covers_userinfo_path_and_innocuous_query_values(self) -> None:
        payload = base_payload()
        raw_token = "ghp_123456789012345678901234567890"
        raw_bearer = "Bearer abcdefghijklmnop"
        payload["search"]["sources"][0]["items"] = [{
            "number": 11,
            "url": f"https://user:password@github.com/example/project/{raw_token}?q={raw_bearer}",
            "state": "open",
            "title": "Unsafe URL evidence",
            "relationship": "unrelated",
        }]
        report = self.module.build_report(payload)
        encoded = json.dumps(report)
        self.assertEqual(report["status"], "blocked")
        self.assertNotIn("password", encoded)
        self.assertNotIn(raw_token, encoded)
        self.assertNotIn(raw_bearer, encoded)

    def test_malformed_source_entry_is_structured_blocked_report(self) -> None:
        payload = base_payload()
        payload["search"]["sources"] = [None]
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item["code"] == "invalid_search_source" for item in report["blockers"]))

    def test_non_list_items_are_structured_blocked_report(self) -> None:
        payload = base_payload()
        payload["search"]["sources"][0]["items"] = 1
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item["code"] == "search_source_items_invalid" for item in report["blockers"]))

    def test_invalid_relationship_enum_blocks_instead_of_inference(self) -> None:
        payload = base_payload()
        payload["search"]["sources"][0]["items"] = [{
            "number": 12,
            "url": "https://github.com/example/project/issues/12",
            "title": "Potential duplicate",
            "relationship": "duplicte",
        }]
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item["code"] == "invalid_search_item_relationship" for item in report["blockers"]))

    def test_narrowed_source_kinds_require_explicit_omission_justification(self) -> None:
        payload = base_payload()
        payload["search"]["required_source_kinds"] = ["issues"]
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item["code"] == "required_search_source_omission_not_justified" for item in report["blockers"]))

    def test_openclaw_continuation_fixture_routes_issue_106704(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        report = self.module.build_report(payload)
        self.assertEqual(report["status"], "duplicate")
        self.assertEqual(report["matches"][0]["number"], 106704)
        self.assertEqual(report["matches"][0]["url"], "https://github.com/openclaw/openclaw/issues/106704")

    def test_cli_writes_json_and_markdown_and_returns_duplicate_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            report_path = directory_path / "report.json"
            markdown_path = directory_path / "evidence.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(FIXTURE),
                    "--output",
                    str(report_path),
                    "--markdown-output",
                    str(markdown_path),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 3)
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["status"], "duplicate")
            self.assertIn("106704", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
