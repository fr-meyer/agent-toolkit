#!/usr/bin/env python3
"""Canonical fail-closed Pullfrog review evidence contract.

This module evaluates one exact repository/PR/base/head identity. A native clean
verdict requires a marker-bearing Pullfrog review, zero findings, zero unresolved
Pullfrog review threads, and exact-head app-bound Pullfrog checks from one check
suite. A scoped review-only verdict validates the same review/thread evidence
without requiring checks that its token cannot publish. Finding verdicts remain
eligible for bounded remediation, but never for merge. Raw review or comment
text is represented only by digests in receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any

CONTRACT_SCHEMA = "pullfrog-review-contract.v2"
GATE_SCHEMA = "pullfrog-review-gate-publication.v3"
SNAPSHOT_SCHEMA = "pullfrog-review-contract-snapshot.v1"
REVIEW_MARKER = "PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ"
PULLFROG_LOGIN = "pullfrog[bot]"
PULLFROG_APP = "pullfrog"
PULLFROG_CHECK = "pullfrog"
PULLFROG_APPROVAL_CHECK = "pullfrog-approval"
GATE_NAME = "pullfrog-review-gate"
GATE_APP = "github-actions"
NATIVE_EVIDENCE_PROFILE = "native"
REVIEW_ONLY_EVIDENCE_PROFILE = "review-only"
EVIDENCE_PROFILES = frozenset(
    {NATIVE_EVIDENCE_PROFILE, REVIEW_ONLY_EVIDENCE_PROFILE}
)
REVIEW_BASE_REFS = frozenset({"dev", "main"})
CLEAN_REVIEW_RE = re.compile(
    r"^\s*(?:>\s*)?(?:✅\s*)?no new issues found\.?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_PAGES = 5
MAX_ITEMS = 500
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
OWNER_RE = re.compile(r"^(?=.{1,39}$)(?!-)(?!.*--)[A-Za-z0-9-]+(?<!-)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
CHECK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/()\[\]-]{0,199}$")
APP_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
THREAD_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_+=/-]{1,256}$")
STATUS_PRIORITY = {
    "missing": 7,
    "timed_out": 6,
    "cancelled": 5,
    "failure": 4,
    "pending": 3,
    "skipped": 2,
    "success": 1,
}


class ReviewContractError(Exception):
    """Sanitized stable error code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_slug(value: str) -> str:
    if value.count("/") != 1:
        return ""
    owner, repository = value.split("/", 1)
    if not OWNER_RE.fullmatch(owner):
        return ""
    if not REPOSITORY_RE.fullmatch(repository) or repository in {".", ".."}:
        return ""
    return f"{owner.casefold()}/{repository.casefold()}"


def valid_branch(value: str) -> bool:
    if not value or not BRANCH_RE.fullmatch(value):
        return False
    if value.startswith(("-", "/", "refs/")) or value.endswith(("/", ".")):
        return False
    if value == "@" or "@{" in value or ".." in value or "//" in value:
        return False
    return all(
        component and not component.startswith(".") and not component.endswith(".lock")
        for component in value.split("/")
    )


def valid_path(value: str) -> bool:
    if (
        not value
        or "\\" in value
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or "/./" in value
        or value.startswith("./")
        or any(ord(character) < 32 for character in value)
    ):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def normalize_identity(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    slug = canonical_slug(_text(item.get("repository_slug") or item.get("slug")))
    head_repository_slug = canonical_slug(_text(item.get("head_repository_slug")))
    base_repository_slug = canonical_slug(
        _text(item.get("base_repository_slug") or item.get("repository_slug") or item.get("slug"))
    )
    return {
        "repository_slug": slug,
        "pr_number": _integer(item.get("pr_number")),
        "base_ref": _text(item.get("base_ref")),
        "base_sha": _text(item.get("base_sha")),
        "head_ref": _text(item.get("head_ref")),
        "head_sha": _text(item.get("head_sha")),
        "head_repository_slug": head_repository_slug,
        "base_repository_slug": base_repository_slug,
    }


def identity_from_pull_request(repository_slug: str, pr: dict[str, Any]) -> dict[str, Any]:
    head = _mapping(pr.get("head"))
    base = _mapping(pr.get("base"))
    return normalize_identity(
        {
            "repository_slug": repository_slug,
            "pr_number": _integer(pr.get("number")),
            "base_ref": _text(base.get("ref")),
            "base_sha": _text(base.get("sha")),
            "head_ref": _text(head.get("ref")),
            "head_sha": _text(head.get("sha")),
            "head_repository_slug": _text(_mapping(head.get("repo")).get("full_name")),
            "base_repository_slug": _text(_mapping(base.get("repo")).get("full_name"))
            or repository_slug,
        }
    )


def _valid_review_identity(identity: dict[str, Any]) -> bool:
    return bool(
        identity["repository_slug"]
        and identity["head_repository_slug"]
        and identity["base_repository_slug"] == identity["repository_slug"]
        and identity["base_ref"] in REVIEW_BASE_REFS
        and (_integer(identity.get("pr_number")) or 0) > 0
        and valid_branch(_text(identity.get("base_ref")))
        and valid_branch(_text(identity.get("head_ref")))
        and SHA_RE.fullmatch(_text(identity.get("base_sha")))
        and SHA_RE.fullmatch(_text(identity.get("head_sha")))
    )


def _valid_gate_identity(identity: dict[str, Any]) -> bool:
    return bool(
        _valid_review_identity(identity)
        and identity["head_repository_slug"] == identity["repository_slug"]
    )


def safe_status(status: str, conclusion: str) -> str:
    if status != "completed":
        return "pending"
    return {
        "success": "success",
        "failure": "failure",
        "action_required": "failure",
        "neutral": "failure",
        "stale": "failure",
        "startup_failure": "failure",
        "cancelled": "cancelled",
        "timed_out": "timed_out",
        "skipped": "skipped",
    }.get(conclusion, "missing")


def check_rule(value: Any) -> tuple[str, str] | None:
    item = _mapping(value)
    name = _text(item.get("name"))
    app_slug = _text(item.get("app_slug"))
    if not CHECK_NAME_RE.fullmatch(name) or not APP_SLUG_RE.fullmatch(app_slug):
        return None
    return name, app_slug


def select_check(
    check_runs: list[Any], head_sha: str, name: str, app_slug: str
) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    spoofed = 0
    stale = 0
    for raw in check_runs:
        item = _mapping(raw)
        if _text(item.get("name")) != name:
            continue
        if _text(_mapping(item.get("app")).get("slug")) != app_slug:
            spoofed += 1
            continue
        if _text(item.get("head_sha")) != head_sha:
            stale += 1
            continue
        check_id = _integer(item.get("id"))
        if check_id is None or check_id < 1:
            continue
        eligible.append(item)
    if not eligible:
        return {
            "name": name,
            "app_slug": app_slug,
            "status": "missing",
            "head_sha": head_sha,
            "check_run_id": None,
            "check_suite_id": None,
            "external_id": "",
            "superseded_count": 0,
            "spoofed_count": spoofed,
            "stale_count": stale,
        }
    selected = max(eligible, key=lambda item: _integer(item.get("id")) or 0)
    return {
        "name": name,
        "app_slug": app_slug,
        "status": safe_status(_text(selected.get("status")), _text(selected.get("conclusion"))),
        "head_sha": head_sha,
        "check_run_id": _integer(selected.get("id")),
        "check_suite_id": _integer(_mapping(selected.get("check_suite")).get("id")),
        "external_id": _text(selected.get("external_id")),
        "superseded_count": len(eligible) - 1,
        "spoofed_count": spoofed,
        "stale_count": stale,
    }


def gate_external_id(
    identity: Any,
    evidence_profile: str,
    evidence_digest: str,
) -> str:
    item = normalize_identity(identity)
    if (
        not _valid_gate_identity(item)
        or evidence_profile not in EVIDENCE_PROFILES
        or not re.fullmatch(r"[0-9a-f]{64}", evidence_digest)
    ):
        raise ReviewContractError("invalid_review_gate_identity")
    return (
        f"pullfrog-review-gate:v3:{item['repository_slug']}:{item['pr_number']}:"
        f"{item['base_sha']}:{item['head_sha']}:{evidence_profile}:{evidence_digest}"
    )


def gate_identity_prefix(identity: Any) -> str:
    item = normalize_identity(identity)
    if not _valid_gate_identity(item):
        raise ReviewContractError("invalid_review_gate_identity")
    return (
        f"pullfrog-review-gate:v3:{item['repository_slug']}:{item['pr_number']}:"
        f"{item['base_sha']}:{item['head_sha']}:"
    )


def select_gate(
    check_runs: list[Any],
    identity: Any,
    contracts: list[Any],
) -> dict[str, Any]:
    item = normalize_identity(identity)
    selected = select_check(check_runs, item["head_sha"], GATE_NAME, GATE_APP)
    candidates: dict[str, dict[str, str]] = {}
    gate_identity_valid = _valid_gate_identity(item)
    for raw in contracts:
        contract = _mapping(raw)
        contract_status = _text(contract.get("status"))
        profile = _text(contract.get("evidence_profile"))
        digest = _text(contract.get("evidence_digest"))
        if (
            contract.get("schema") != CONTRACT_SCHEMA
            or contract_status not in {"clean", "findings"}
            or contract.get("blockers") != []
            or normalize_identity(contract.get("identity")) != item
            or profile not in EVIDENCE_PROFILES
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not gate_identity_valid
        ):
            continue
        external_id = gate_external_id(item, profile, digest)
        candidates[external_id] = {
            "contract_status": contract_status,
            "evidence_profile": profile,
            "evidence_digest": digest,
        }
    selected_external_id = _text(selected.get("external_id"))
    if selected["check_run_id"] and selected_external_id not in candidates:
        selected = dict(selected)
        selected["status"] = "missing"
        selected["external_id_mismatch"] = True
    else:
        selected["external_id_mismatch"] = False
    matched = candidates.get(selected_external_id, {})
    selected["contract_status"] = matched.get("contract_status", "")
    selected["evidence_profile"] = matched.get("evidence_profile", "")
    selected["evidence_digest"] = matched.get("evidence_digest", "")
    selected["expected_external_ids"] = sorted(candidates)
    return selected


def valid_complete_review(review: dict[str, Any], head_sha: str) -> bool:
    body = _text(review.get("body"))
    return bool(
        (_integer(review.get("id")) or 0) > 0
        and _text(review.get("commit_id")) == head_sha
        and _text(_mapping(review.get("user")).get("login")).casefold()
        == PULLFROG_LOGIN
        and _text(review.get("submitted_at"))
        and body.strip()
        and REVIEW_MARKER in body
    )


def select_complete_review(reviews: list[Any], head_sha: str) -> dict[str, Any]:
    eligible = [
        _mapping(raw)
        for raw in reviews
        if valid_complete_review(_mapping(raw), head_sha)
    ]
    if not eligible:
        return {}
    return max(
        eligible,
        key=lambda item: (_text(item.get("submitted_at")), _integer(item.get("id")) or 0),
    )


def _review_findings(
    review: dict[str, Any],
    comments: list[Any],
    approval_status: str,
    head_sha: str,
    evidence_profile: str,
) -> tuple[list[dict[str, Any]], str, int, list[str]]:
    review_id = _integer(review.get("id"))
    review_body = " ".join(_text(review.get("body")).split()).casefold()
    body_digest = _digest(review_body)
    records: list[dict[str, Any]] = []
    blockers: list[str] = []
    for raw in comments:
        item = _mapping(raw)
        if _integer(item.get("pull_request_review_id")) != review_id:
            continue
        if item.get("in_reply_to_id") is not None:
            continue
        if _text(_mapping(item.get("user")).get("login")).casefold() != PULLFROG_LOGIN:
            continue
        comment_id = _integer(item.get("id"))
        path = _text(item.get("path"))
        line = _integer(item.get("line")) or _integer(item.get("original_line")) or 1
        if _text(item.get("commit_id")) != head_sha:
            blockers.append("stale_pullfrog_review_comment")
            continue
        body = " ".join(_text(item.get("body")).split()).casefold()
        if comment_id is None or comment_id < 1 or not valid_path(path) or line < 1 or not body:
            blockers.append("invalid_pullfrog_review_comment")
            continue
        body_digest_comment = _digest(body)
        semantic_id = _digest(
            {"path": path, "line": line, "body_digest": body_digest_comment}
        )
        records.append(
            {
                "id": "finding-" + semantic_id,
                "severity": "high",
                "path": path,
                "line": line,
                "summary": "pullfrog-comment-" + body_digest_comment,
            }
        )
    records.sort(key=lambda item: (item["path"], item["line"], item["id"]))
    findings: list[dict[str, Any]] = []
    if evidence_profile == REVIEW_ONLY_EVIDENCE_PROFILE:
        findings = records
        if not findings and review and not CLEAN_REVIEW_RE.search(_text(review.get("body"))):
            findings = [
                {
                    "id": "review-summary-" + body_digest,
                    "severity": "high",
                    "path": "PULL_REQUEST.md",
                    "line": 1,
                    "summary": "pullfrog-review-" + body_digest,
                }
            ]
    elif approval_status == "failure":
        findings = records
        if not findings and review:
            findings = [
                {
                    "id": "review-summary-" + body_digest,
                    "severity": "high",
                    "path": "PULL_REQUEST.md",
                    "line": 1,
                    "summary": "pullfrog-review-" + body_digest,
                }
            ]
    elif approval_status == "success" and records:
        blockers.append("pullfrog_approval_comment_mismatch")
    output_digest = _digest(
        {
            "state": _text(review.get("state")).casefold(),
            "body_digest": body_digest,
            "comment_fingerprints": [
                _digest({"path": item["path"], "line": item["line"], "summary": item["summary"]})
                for item in records
            ],
        }
    )
    return findings, output_digest, len(records), sorted(set(blockers))


def _thread_root(thread: dict[str, Any]) -> dict[str, Any]:
    comments = _mapping(thread.get("comments"))
    nodes = _list(comments.get("nodes")) if comments else _list(thread.get("comments"))
    return _mapping(nodes[0]) if nodes else _mapping(thread.get("root"))


def unresolved_pullfrog_threads(threads: list[Any]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for raw in threads:
        item = _mapping(raw)
        root = _thread_root(item)
        author = _text(_mapping(root.get("author") or root.get("user")).get("login")).casefold()
        if author != PULLFROG_LOGIN or item.get("isResolved") is True or item.get("is_resolved") is True:
            continue
        review_id = _integer(_mapping(root.get("pullRequestReview") or root.get("review")).get("databaseId"))
        if review_id is None:
            review_id = _integer(root.get("pull_request_review_id"))
        node_id = _text(item.get("id"))
        unresolved.append(
            {
                "node_id": node_id if THREAD_NODE_ID_RE.fullmatch(node_id) else "",
                "review_id": review_id or 0,
                "path": _text(item.get("path")),
                "line": _integer(item.get("line")) or _integer(item.get("originalLine")) or 0,
                "outdated": bool(item.get("isOutdated") or item.get("is_outdated")),
            }
        )
    unresolved.sort(key=lambda item: (item["review_id"], item["path"], item["line"]))
    return unresolved


def evaluate_contract(
    snapshot: dict[str, Any],
    evidence_profile: str = NATIVE_EVIDENCE_PROFILE,
) -> dict[str, Any]:
    blockers: list[str] = []
    if evidence_profile not in EVIDENCE_PROFILES:
        blockers.append("invalid_review_evidence_profile")
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        blockers.append("invalid_review_contract_snapshot")
    expected = normalize_identity(snapshot.get("expected_identity"))
    observed = normalize_identity(snapshot.get("observed_identity"))
    if not _valid_review_identity(expected):
        blockers.append("invalid_expected_review_identity")
    if not _valid_review_identity(observed):
        blockers.append("invalid_observed_review_identity")
    if expected != observed:
        blockers.append("review_identity_drift")

    head_sha = observed["head_sha"]
    check_runs = _list(snapshot.get("check_runs"))
    pullfrog = select_check(check_runs, head_sha, PULLFROG_CHECK, PULLFROG_APP)
    approval = select_check(check_runs, head_sha, PULLFROG_APPROVAL_CHECK, PULLFROG_APP)
    for name, check in (("pullfrog", pullfrog), ("pullfrog_approval", approval)):
        if check["spoofed_count"]:
            blockers.append(f"{name}_check_spoofed")
        if check["stale_count"]:
            blockers.append(f"{name}_check_stale")
    if evidence_profile == NATIVE_EVIDENCE_PROFILE:
        if pullfrog["status"] != "success":
            blockers.append(f"pullfrog_check_{pullfrog['status']}")
        if approval["status"] not in {"success", "failure"}:
            blockers.append(f"pullfrog_approval_check_{approval['status']}")
        if (
            pullfrog["check_suite_id"] is None
            or approval["check_suite_id"] is None
            or pullfrog["check_suite_id"] != approval["check_suite_id"]
        ):
            blockers.append("pullfrog_check_suite_mismatch")

    reviews = _list(snapshot.get("reviews"))
    complete_review = select_complete_review(reviews, head_sha)
    partial_count = sum(
        1
        for raw in reviews
        if _text(_mapping(raw).get("commit_id")) == head_sha
        and _text(_mapping(_mapping(raw).get("user")).get("login")).casefold()
        == PULLFROG_LOGIN
        and not valid_complete_review(_mapping(raw), head_sha)
    )
    if not complete_review:
        blockers.append("missing_complete_primary_verdict")
    findings, output_digest, comment_count, comment_blockers = _review_findings(
        complete_review,
        _list(snapshot.get("review_comments")),
        approval["status"],
        head_sha,
        evidence_profile,
    )
    blockers.extend(comment_blockers)
    unresolved = unresolved_pullfrog_threads(_list(snapshot.get("review_threads")))

    structural_blockers = sorted(set(blockers))
    if structural_blockers:
        status = "incomplete"
    elif findings:
        status = "findings"
    elif unresolved:
        status = "reconciliation_required"
        structural_blockers.append("unresolved_pullfrog_review_threads")
    else:
        status = "clean"

    review_id = _integer(complete_review.get("id")) or 0
    evidence_digest = _digest(
        {
            "evidence_profile": evidence_profile,
            "identity": observed,
            "review_id": review_id,
            "review_output_digest": output_digest,
            "finding_ids": [item["id"] for item in findings],
            "unresolved_threads": unresolved,
            "pullfrog_check": {
                key: pullfrog.get(key)
                for key in (
                    "status",
                    "check_run_id",
                    "check_suite_id",
                    "external_id",
                )
            },
            "approval_check": {
                key: approval.get(key)
                for key in (
                    "status",
                    "check_run_id",
                    "check_suite_id",
                    "external_id",
                )
            },
        }
    )
    gate_id = (
        gate_external_id(observed, evidence_profile, evidence_digest)
        if _valid_gate_identity(observed)
        else ""
    )
    return {
        "schema": CONTRACT_SCHEMA,
        "evidence_profile": evidence_profile,
        "status": status,
        "blockers": sorted(set(structural_blockers)),
        "identity": observed,
        "review": {
            "review_id": review_id,
            "head_sha": head_sha,
            "finding_count": len(findings),
            "findings": findings,
            "comment_count": comment_count,
            "partial_review_count": partial_count,
            "output_digest": output_digest,
        },
        "threads": {
            "unresolved_pullfrog_count": len(unresolved),
            "unresolved_pullfrog_digest": _digest(unresolved),
        },
        "checks": {
            "pullfrog": pullfrog,
            "pullfrog_approval": approval,
        },
        "gate": {
            "name": GATE_NAME,
            "app_slug": GATE_APP,
            "external_id": gate_id,
            "conclusion": "success" if status == "clean" else "failure",
        },
        "evidence_digest": evidence_digest,
        "raw_text_included": False,
    }


THREAD_QUERY = """
query PullfrogReviewThreads($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first: 1) {
            nodes {
              databaseId
              author { login }
              pullRequestReview { databaseId }
            }
          }
        }
      }
    }
  }
}
"""


def collect_review_threads(client: Any, identity: Any) -> list[Any]:
    item = normalize_identity(identity)
    owner, name = item["repository_slug"].split("/", 1)
    result: list[Any] = []
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        payload = client.graphql(
            THREAD_QUERY,
            {"owner": owner, "name": name, "number": item["pr_number"], "cursor": cursor},
        )
        data = payload.get("data")
        repository = data.get("repository") if isinstance(data, dict) else None
        pull_request = (
            repository.get("pullRequest") if isinstance(repository, dict) else None
        )
        connection = (
            pull_request.get("reviewThreads")
            if isinstance(pull_request, dict)
            else None
        )
        if (
            not isinstance(connection, dict)
            or not isinstance(connection.get("nodes"), list)
            or not isinstance(connection.get("pageInfo"), dict)
        ):
            raise ReviewContractError("invalid_review_thread_response")
        nodes = connection["nodes"]
        result.extend(nodes)
        if len(result) > MAX_ITEMS:
            raise ReviewContractError("review_thread_collection_too_large")
        page_info = connection["pageInfo"]
        if not isinstance(page_info.get("hasNextPage"), bool):
            raise ReviewContractError("invalid_review_thread_pagination")
        if not page_info.get("hasNextPage"):
            return result
        cursor = _text(page_info.get("endCursor"))
        if not cursor:
            raise ReviewContractError("invalid_review_thread_pagination")
    raise ReviewContractError("review_thread_pagination_limit")


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewContractError("invalid_json_file") from exc
    if not isinstance(value, dict):
        raise ReviewContractError("invalid_json_root")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    fixture = sub.add_parser("evaluate-snapshot")
    fixture.add_argument("--snapshot", required=True)
    fixture.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        receipt = evaluate_contract(_load_object(Path(args.snapshot)))
        _write_object(Path(args.out), receipt)
    except ReviewContractError as exc:
        print(exc.code, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
