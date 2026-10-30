#!/usr/bin/env python3
"""Read-only coordinator for one Pullfrog exact-head automation decision.

The coordinator can evaluate a captured GitHub snapshot or collect one through
bounded GitHub REST GET requests. It never invokes a provider, starts a fix,
changes a check, commits, pushes, approves, merges, reruns, releases, deploys,
changes settings, or deletes a branch. Its only output is a sanitized receipt.
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
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pullfrog_cycle_contract as cycle_contract  # noqa: E402
import pullfrog_destination_guard as destination_guard  # noqa: E402
import pullfrog_review_contract as review_contract  # noqa: E402
import pullfrog_trusted_author_policy as trusted_author_policy  # noqa: E402

SNAPSHOT_SCHEMA = "pullfrog-cloud-snapshot.v1"
RECEIPT_SCHEMA = "pullfrog-cloud-coordinator-receipt.v1"
HISTORY_SCHEMA = "pullfrog-cloud-history.v1"
MODE = "dry-run"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_PAGES = 5
MAX_ITEMS = 500
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CHECK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/()\[\]-]{0,199}$")
APP_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
EVENT_KINDS = {
    "pullfrog_review_completed",
    "required_evidence_completed",
    "workflow_dispatch",
}
PULLFROG_LOGIN = review_contract.PULLFROG_LOGIN
PULLFROG_APP = review_contract.PULLFROG_APP
PULLFROG_CHECK = review_contract.PULLFROG_CHECK
PULLFROG_APPROVAL_CHECK = review_contract.PULLFROG_APPROVAL_CHECK
STATUS_PRIORITY = {
    "missing": 7,
    "timed_out": 6,
    "cancelled": 5,
    "failure": 4,
    "pending": 3,
    "skipped": 2,
    "success": 1,
}


class CoordinatorError(Exception):
    """Sanitized coordinator error with a stable machine-readable code."""

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


def _valid_slug(value: str) -> bool:
    return bool(cycle_contract._canonical_slug(value))


def _valid_path(value: str) -> bool:
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


def _safe_status(status: str, conclusion: str) -> str:
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


def _worst_status(statuses: Iterable[str]) -> str:
    values = list(statuses)
    if not values:
        return "missing"
    return max(values, key=lambda item: STATUS_PRIORITY.get(item, 99))


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoordinatorError("invalid_json_file") from exc
    if not isinstance(value, dict):
        raise CoordinatorError("invalid_json_root")
    return value


def _empty_history() -> dict[str, Any]:
    return {
        "schema": HISTORY_SCHEMA,
        "cycle_number": 0,
        "completed_claim_keys": [],
        "remediation_source_heads": [],
        "finding_set_digests": [],
        "output_digests": [],
    }


def _validated_history(value: Any) -> dict[str, Any]:
    history = _mapping(value)
    if not history:
        return _empty_history()
    if history.get("schema") != HISTORY_SCHEMA:
        raise CoordinatorError("invalid_history_schema")
    cycle_number = _integer(history.get("cycle_number"))
    if cycle_number is None or not 0 <= cycle_number <= cycle_contract.MAX_CYCLES:
        raise CoordinatorError("invalid_history_cycle")
    result = {"schema": HISTORY_SCHEMA, "cycle_number": cycle_number}
    for key in (
        "completed_claim_keys",
        "remediation_source_heads",
        "finding_set_digests",
        "output_digests",
    ):
        value_list = history.get(key)
        if not isinstance(value_list, list) or any(not isinstance(item, str) for item in value_list):
            raise CoordinatorError("invalid_history_values")
        result[key] = list(value_list)
    return result


def _identity_from_pr(
    repository_slug: str,
    pr: dict[str, Any],
    default_branch: str,
    protected_refs: list[str],
) -> dict[str, Any]:
    head = _mapping(pr.get("head"))
    base = _mapping(pr.get("base"))
    head_repo = _mapping(head.get("repo"))
    base_repo = _mapping(base.get("repo"))
    return {
        "slug": repository_slug,
        "pr_number": _integer(pr.get("number")),
        "base_ref": _text(base.get("ref")),
        "base_sha": _text(base.get("sha")),
        "head_ref": _text(head.get("ref")),
        "head_sha": _text(head.get("sha")),
        "head_repository_slug": _text(head_repo.get("full_name")),
        "base_repository_slug": _text(base_repo.get("full_name")) or repository_slug,
        "default_branch": default_branch,
        "protected_refs": protected_refs,
    }


def _check_rule(value: Any) -> tuple[str, str] | None:
    item = _mapping(value)
    name = _text(item.get("name"))
    app_slug = _text(item.get("app_slug"))
    if not CHECK_NAME_RE.fullmatch(name) or not APP_SLUG_RE.fullmatch(app_slug):
        return None
    return name, app_slug


def _select_check(
    check_runs: list[Any],
    head_sha: str,
    name: str,
    app_slug: str,
) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    spoofed = 0
    stale = 0
    for raw in check_runs:
        item = _mapping(raw)
        if _text(item.get("name")) != name:
            continue
        observed_app = _text(_mapping(item.get("app")).get("slug"))
        if observed_app != app_slug:
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
            "superseded_count": 0,
            "spoofed_count": spoofed,
            "stale_count": stale,
        }
    eligible.sort(key=lambda item: _integer(item.get("id")) or 0)
    selected = eligible[-1]
    suite_id = _integer(_mapping(selected.get("check_suite")).get("id"))
    return {
        "name": name,
        "app_slug": app_slug,
        "status": _safe_status(_text(selected.get("status")), _text(selected.get("conclusion"))),
        "head_sha": head_sha,
        "check_run_id": _integer(selected.get("id")),
        "check_suite_id": suite_id,
        "superseded_count": len(eligible) - 1,
        "spoofed_count": spoofed,
        "stale_count": stale,
    }


def _group_check(
    check_runs: list[Any],
    head_sha: str,
    rules: list[Any],
    canonical_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    parsed = [_check_rule(item) for item in rules]
    blockers: list[str] = []
    if not parsed or any(item is None for item in parsed) or len(set(parsed)) != len(parsed):
        blockers.append(f"invalid_{canonical_name}_check_policy")
        parsed = []
    selected = [
        _select_check(check_runs, head_sha, name, app_slug)
        for name, app_slug in parsed
        if name and app_slug
    ]
    status = _worst_status(item["status"] for item in selected)
    return (
        {"name": canonical_name, "status": status, "head_sha": head_sha},
        selected,
        blockers,
    )


def _select_review(reviews: list[Any], head_sha: str) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    for raw in reviews:
        item = _mapping(raw)
        if _text(_mapping(item.get("user")).get("login")).casefold() != PULLFROG_LOGIN:
            continue
        if _text(item.get("commit_id")) != head_sha:
            continue
        review_id = _integer(item.get("id"))
        if review_id is None or review_id < 1 or not _text(item.get("submitted_at")):
            continue
        eligible.append(item)
    if not eligible:
        return {}
    eligible.sort(key=lambda item: (_text(item.get("submitted_at")), _integer(item.get("id")) or 0))
    return eligible[-1]


def _review_findings(
    review: dict[str, Any],
    comments: list[Any],
    approval_status: str,
    head_sha: str,
) -> tuple[list[dict[str, Any]], str, int, list[str]]:
    review_id = _integer(review.get("id"))
    review_body = " ".join(_text(review.get("body")).split()).casefold()
    body_digest = _digest(review_body)
    comment_records: list[dict[str, Any]] = []
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
        comment_body = " ".join(_text(item.get("body")).split()).casefold()
        if (
            comment_id is None
            or comment_id < 1
            or not _valid_path(path)
            or line < 1
            or not comment_body
        ):
            blockers.append("invalid_pullfrog_review_comment")
            continue
        comment_body_digest = _digest(comment_body)
        semantic_id = _digest(
            {"path": path, "line": line, "body_digest": comment_body_digest}
        )
        comment_records.append(
            {
                "id": "finding-" + semantic_id,
                "severity": "high",
                "path": path,
                "line": line,
                "summary": "pullfrog-comment-" + comment_body_digest,
            }
        )
    comment_records.sort(key=lambda item: (item["path"], item["line"], item["id"]))
    findings: list[dict[str, Any]] = []
    if approval_status == "failure":
        findings = comment_records
        if not findings:
            findings = [
                {
                    "id": "review-summary-" + body_digest,
                    "severity": "high",
                    "path": "PULL_REQUEST.md",
                    "line": 1,
                    "summary": "pullfrog-review-" + body_digest,
                }
            ]
    output_digest = _digest(
        {
            "state": _text(review.get("state")).casefold(),
            "body_digest": body_digest,
            "comment_fingerprints": [
                _digest(
                    {
                        "path": item["path"],
                        "line": item["line"],
                        "summary": item["summary"],
                    }
                )
                for item in comment_records
            ],
        }
    )
    return findings, output_digest, len(comment_records), sorted(set(blockers))


def evaluate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    coordinator_blockers: list[str] = []
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        coordinator_blockers.append("invalid_snapshot_schema")

    repository_slug = _text(snapshot.get("repository_slug"))
    if not _valid_slug(repository_slug):
        coordinator_blockers.append("invalid_repository_slug")
    repository_slug = cycle_contract._canonical_slug(repository_slug)

    event = _mapping(snapshot.get("event"))
    event_kind = _text(event.get("kind"))
    delivery_id = _text(event.get("delivery_id"))
    event_head_sha = _text(event.get("head_sha"))
    if event_kind not in EVENT_KINDS:
        coordinator_blockers.append("invalid_event_kind")
    if not delivery_id or len(delivery_id) > 200:
        coordinator_blockers.append("invalid_delivery_id")
    if not SHA_RE.fullmatch(event_head_sha):
        coordinator_blockers.append("invalid_event_head_sha")

    repository = _mapping(snapshot.get("repository"))
    default_branch = _text(repository.get("default_branch"))
    policy = _mapping(snapshot.get("policy"))
    protected_refs = [_text(item) for item in _list(policy.get("protected_refs"))]
    max_cycles = _integer(policy.get("max_cycles"))
    if max_cycles != cycle_contract.MAX_CYCLES:
        coordinator_blockers.append("invalid_max_cycles_policy")

    expected = _identity_from_pr(
        repository_slug,
        _mapping(snapshot.get("expected_pull_request")),
        default_branch,
        protected_refs,
    )
    observed = _identity_from_pr(
        repository_slug,
        _mapping(snapshot.get("observed_pull_request")),
        default_branch,
        protected_refs,
    )
    expected_pull_request = _mapping(snapshot.get("expected_pull_request"))
    observed_pull_request = _mapping(snapshot.get("observed_pull_request"))
    if _text(observed_pull_request.get("state")) != "open":
        coordinator_blockers.append("pull_request_not_open")
    try:
        authority_decision = trusted_author_policy.evaluate_pull_request_authority(
            trusted_author_policy.load_policy(repository_slug),
            repository_slug,
            expected_pull_request,
            observed_pull_request,
        )
    except trusted_author_policy.TrustedAuthorPolicyError as exc:
        authority_decision = {
            "schema": trusted_author_policy.AUTHORITY_SCHEMA,
            "review_eligible": False,
            "same_repository": False,
            "trusted_author": False,
            "mutation_authorized": False,
            "blockers": [exc.code],
            "identity": {},
            "author_decision": {},
            "policy": {},
        }
    if not authority_decision["review_eligible"]:
        coordinator_blockers.append("pull_request_not_review_eligible")

    head_sha = _text(observed.get("head_sha"))
    check_runs = _list(snapshot.get("check_runs"))
    pullfrog = _select_check(check_runs, head_sha, PULLFROG_CHECK, PULLFROG_APP)
    approval = _select_check(
        check_runs, head_sha, PULLFROG_APPROVAL_CHECK, PULLFROG_APP
    )
    if (
        pullfrog["check_suite_id"] is not None
        and approval["check_suite_id"] is not None
        and pullfrog["check_suite_id"] != approval["check_suite_id"]
    ):
        coordinator_blockers.append("pullfrog_check_suite_mismatch")

    ci, ci_details, ci_blockers = _group_check(
        check_runs, head_sha, _list(policy.get("ci_checks")), "ci"
    )
    speculoos, speculoos_details, speculoos_blockers = _group_check(
        check_runs, head_sha, _list(policy.get("speculoos_checks")), "speculoos"
    )
    coordinator_blockers.extend(ci_blockers)
    coordinator_blockers.extend(speculoos_blockers)
    selected_check_details = {
        "pullfrog": [pullfrog],
        "pullfrog_approval": [approval],
        "ci": ci_details,
        "speculoos": speculoos_details,
    }
    for group, details in selected_check_details.items():
        if any(item["spoofed_count"] for item in details):
            coordinator_blockers.append(f"{group}_check_spoofed")
        if any(item["stale_count"] for item in details):
            coordinator_blockers.append(f"{group}_check_stale")

    contract_snapshot = {
        "schema": review_contract.SNAPSHOT_SCHEMA,
        "expected_identity": expected,
        "observed_identity": observed,
        "reviews": _list(snapshot.get("reviews")),
        "review_comments": _list(snapshot.get("review_comments")),
        "review_threads": _list(snapshot.get("review_threads")),
        "check_runs": check_runs,
    }
    native_review_receipt = review_contract.evaluate_contract(contract_snapshot)
    review_only_receipt = review_contract.evaluate_contract(
        contract_snapshot,
        review_contract.REVIEW_ONLY_EVIDENCE_PROFILE,
    )
    gate = review_contract.select_gate(
        check_runs,
        observed,
        [native_review_receipt, review_only_receipt],
    )
    review_receipt = native_review_receipt
    matched_profile = _text(gate.get("evidence_profile"))
    matched_digest = _text(gate.get("evidence_digest"))
    matched_contract_status = _text(gate.get("contract_status"))
    for candidate in (native_review_receipt, review_only_receipt):
        candidate_status = _text(candidate.get("status"))
        expected_gate_status = (
            "success" if candidate_status == "clean" else "failure"
        )
        if (
            candidate_status in {"clean", "findings"}
            and candidate.get("blockers") == []
            and candidate_status == matched_contract_status
            and gate.get("status") == expected_gate_status
            and candidate.get("evidence_profile") == matched_profile
            and candidate.get("evidence_digest") == matched_digest
        ):
            review_receipt = candidate
            break
    review_evidence = _mapping(review_receipt.get("review"))
    findings = _list(review_evidence.get("findings"))
    output_digest = _text(review_evidence.get("output_digest"))
    review_comment_count = _integer(review_evidence.get("comment_count")) or 0
    if review_receipt.get("status") in {"incomplete", "reconciliation_required"}:
        coordinator_blockers.extend(
            _text(item) for item in _list(review_receipt.get("blockers"))
        )

    history = _validated_history(snapshot.get("history"))
    cycle_number = history["cycle_number"]
    claim_key = f"{repository_slug}:{observed.get('pr_number')}:{head_sha}:{cycle_number}"
    guard_attempt = min(cycle_number + 1, cycle_contract.MAX_CYCLES)

    changed_paths = [
        _text(_mapping(item).get("filename")) for item in _list(snapshot.get("files"))
    ]
    guard_payload = {
        "schema": destination_guard.INPUT_SCHEMA,
        "expected": expected,
        "observed": observed,
        "request": {
            "destination_repository_slug": repository_slug,
            "destination_ref": _text(observed.get("head_ref")),
            "destination_sha": head_sha,
            "attempt": guard_attempt,
            "changed_paths": changed_paths,
        },
        "first_attempt": {
            "destination_repository_slug": repository_slug,
            "destination_ref": _text(expected.get("head_ref")),
            "destination_sha": _text(expected.get("head_sha")),
        },
    }
    guard_receipt = destination_guard.evaluate_guard(guard_payload)
    guard_status = "success" if guard_receipt["status"] == "allowed" else "failure"

    gated_clean = bool(
        gate.get("status") == "success"
        and review_receipt.get("status") == "clean"
        and review_receipt.get("evidence_profile") == gate.get("evidence_profile")
        and review_receipt.get("evidence_digest") == gate.get("evidence_digest")
    )
    gated_findings = bool(
        gate.get("status") == "failure"
        and review_receipt.get("status") == "findings"
        and review_receipt.get("evidence_profile") == gate.get("evidence_profile")
        and review_receipt.get("evidence_digest") == gate.get("evidence_digest")
    )
    effective_pullfrog_status = (
        "success" if gated_clean or gated_findings else pullfrog["status"]
    )
    effective_approval_status = (
        "success"
        if gated_clean
        else "failure"
        if gated_findings
        else approval["status"]
    )
    review_status = effective_pullfrog_status
    if review_receipt.get("status") in {"incomplete", "reconciliation_required"}:
        review_status = "missing"
    cycle_state = {
        "schema": cycle_contract.STATE_SCHEMA,
        "expected": {key: expected[key] for key in (
            "slug", "pr_number", "base_ref", "base_sha", "head_ref", "head_sha", "head_repository_slug"
        )},
        "observed": {key: observed[key] for key in (
            "slug", "pr_number", "base_ref", "base_sha", "head_ref", "head_sha", "head_repository_slug"
        )},
        "event": {
            "delivery_id": delivery_id,
            "kind": event_kind,
            "head_sha": event_head_sha,
        },
        "policy": {"max_cycles": max_cycles},
        "cycle": {"number": cycle_number, "claim_key": claim_key},
        "history": {
            key: history[key]
            for key in (
                "completed_claim_keys",
                "remediation_source_heads",
                "finding_set_digests",
                "output_digests",
            )
        },
        "review": {
            "status": review_status,
            "head_sha": _text(review_evidence.get("head_sha")) or head_sha,
            "review_id": str(_integer(review_evidence.get("review_id")) or 0),
            "output_digest": output_digest,
            "findings": findings,
        },
        "checks": [
            {
                "name": "pullfrog",
                "status": effective_pullfrog_status,
                "head_sha": head_sha,
            },
            {
                "name": "pullfrog-approval",
                "status": effective_approval_status,
                "head_sha": head_sha,
            },
            ci,
            speculoos,
            {"name": "destination-guard", "status": guard_status, "head_sha": head_sha},
        ],
    }
    decision = cycle_contract.evaluate_state(cycle_state)

    coordinator_blockers = sorted(set(coordinator_blockers))
    effective_status = "stopped" if coordinator_blockers else decision["status"]
    would_action = "none" if coordinator_blockers else decision["action"]
    manual_governance_required = bool(
        "forbidden_changed_path" in _list(guard_receipt.get("blockers"))
        or _text(observed.get("base_ref")) in {"main", "master"}
    )
    policy_decision = {
        "review_eligible": authority_decision["review_eligible"],
        "same_repository": authority_decision["same_repository"],
        "trusted_author": authority_decision["trusted_author"],
        "mutation_authorized": authority_decision["mutation_authorized"],
        "remediation_allowed": bool(
            authority_decision["mutation_authorized"]
            and effective_status == "remediation_ready"
            and would_action == "start_remediation"
            and guard_receipt.get("status") == "allowed"
        ),
        "merge_allowed": bool(
            authority_decision["mutation_authorized"]
            and effective_status == "clean"
            and would_action == "complete"
            and gate.get("status") == "success"
            and _text(observed.get("base_ref")) not in {"main", "master"}
        ),
        "manual_governance_required": manual_governance_required,
    }
    return {
        "schema": RECEIPT_SCHEMA,
        "mode": MODE,
        "snapshot_digest": _digest(snapshot),
        "status": effective_status,
        "would_action": would_action,
        "executed_action": "none",
        "coordinator_blockers": coordinator_blockers,
        "mutation": {
            "enabled": False,
            "attempted": False,
            "repository_write": False,
            "provider_invocation": False,
            "approval": False,
            "merge": False,
            "rerun": False,
            "release": False,
            "deployment": False,
            "settings_change": False,
            "branch_deletion": False,
        },
        "identity": {
            "repository_slug": repository_slug,
            "pr_number": observed.get("pr_number"),
            "base_ref": observed.get("base_ref"),
            "base_sha": observed.get("base_sha"),
            "head_ref": observed.get("head_ref"),
            "head_sha": head_sha,
            "head_repository_slug": observed.get("head_repository_slug"),
            "event_head_sha": event_head_sha,
        },
        "destination_policy": {
            "default_branch": default_branch,
            "protected_refs": protected_refs,
        },
        "event": {
            "kind": event_kind,
            "delivery_id_digest": _digest(delivery_id),
        },
        "collection": {
            "reviews_seen": len(_list(snapshot.get("reviews"))),
            "review_comments_seen": len(_list(snapshot.get("review_comments"))),
            "selected_review_comment_count": review_comment_count,
            "unresolved_pullfrog_thread_count": _integer(
                _mapping(review_receipt.get("threads")).get("unresolved_pullfrog_count")
            )
            or 0,
            "check_runs_seen": len(check_runs),
            "changed_paths_count": len(changed_paths),
            "changed_paths_digest": _digest(sorted(changed_paths)),
        },
        "checks": {
            "pullfrog": pullfrog,
            "pullfrog_approval": approval,
            "pullfrog_review_gate": gate,
            "ci": ci_details,
            "speculoos": speculoos_details,
        },
        "review_contract": review_receipt,
        "authority_decision": authority_decision,
        "policy_decision": policy_decision,
        "destination_guard": guard_receipt,
        "cycle_decision": decision,
    }


class GitHubReadClient:
    """Bounded GET-only GitHub REST client."""

    def __init__(self, api_url: str, token: str, repository_slug: str):
        parsed = urllib.parse.urlparse(api_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise CoordinatorError("invalid_github_api_url")
        if parsed.query or parsed.fragment:
            raise CoordinatorError("invalid_github_api_url")
        if not token:
            raise CoordinatorError("missing_github_token")
        if not _valid_slug(repository_slug):
            raise CoordinatorError("invalid_repository_slug")
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.repository_slug = cycle_contract._canonical_slug(repository_slug)
        self.allowed_prefix = f"/repos/{self.repository_slug}"

    def get(self, path: str) -> Any:
        parsed_path = urllib.parse.urlparse(path)
        if (
            parsed_path.scheme
            or parsed_path.netloc
            or parsed_path.path not in {self.allowed_prefix}
            and not parsed_path.path.startswith(self.allowed_prefix + "/")
        ):
            raise CoordinatorError("forbidden_github_api_path")
        request = urllib.request.Request(
            self.api_url + path,
            method="GET",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "agent-toolkit-pullfrog-cloud-coordinator",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise CoordinatorError("github_api_read_failed") from exc
        if len(data) > MAX_RESPONSE_BYTES:
            raise CoordinatorError("github_api_response_too_large")
        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CoordinatorError("invalid_github_api_response") from exc

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.api_url + "/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "agent-toolkit-pullfrog-cloud-coordinator",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise CoordinatorError("github_graphql_read_failed") from exc
        if len(data) > MAX_RESPONSE_BYTES:
            raise CoordinatorError("github_api_response_too_large")
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CoordinatorError("invalid_github_api_response") from exc
        if not isinstance(value, dict) or value.get("errors"):
            raise CoordinatorError("invalid_github_graphql_response")
        return value

    def paginated(self, path: str) -> list[Any]:
        items: list[Any] = []
        for page in range(1, MAX_PAGES + 1):
            separator = "&" if "?" in path else "?"
            value = self.get(f"{path}{separator}per_page=100&page={page}")
            if not isinstance(value, list):
                raise CoordinatorError("invalid_github_api_collection")
            items.extend(value)
            if len(items) > MAX_ITEMS:
                raise CoordinatorError("github_api_collection_too_large")
            if len(value) < 100:
                return items
        raise CoordinatorError("github_api_pagination_limit")


def collect_github_snapshot(
    *,
    api_url: str,
    token: str,
    repository_slug: str,
    pr_number: int,
    expected_head_sha: str,
    event_kind: str,
    delivery_id: str,
    protected_refs: list[str],
    ci_rules: list[dict[str, str]],
    speculoos_rules: list[dict[str, str]],
    history: dict[str, Any],
) -> dict[str, Any]:
    if pr_number < 1 or not SHA_RE.fullmatch(expected_head_sha):
        raise CoordinatorError("invalid_event_context")
    client = GitHubReadClient(api_url, token, repository_slug)
    prefix = f"/repos/{client.repository_slug}"
    repository = _mapping(client.get(prefix))
    expected_pr = _mapping(client.get(f"{prefix}/pulls/{pr_number}"))
    default_branch = _text(repository.get("default_branch"))
    base_ref = _text(_mapping(expected_pr.get("base")).get("ref"))
    effective_protected_refs = sorted(
        {
            ref
            for ref in (*protected_refs, default_branch, base_ref)
            if ref
        }
    )
    reviews = client.paginated(f"{prefix}/pulls/{pr_number}/reviews")
    comments = client.paginated(f"{prefix}/pulls/{pr_number}/comments")
    review_threads = review_contract.collect_review_threads(
        client,
        _identity_from_pr(client.repository_slug, expected_pr, default_branch, effective_protected_refs),
    )
    files = client.paginated(f"{prefix}/pulls/{pr_number}/files")
    check_payload = _mapping(
        client.get(f"{prefix}/commits/{expected_head_sha}/check-runs?per_page=100")
    )
    check_runs = _list(check_payload.get("check_runs"))
    if _integer(check_payload.get("total_count")) not in {None, len(check_runs)}:
        raise CoordinatorError("check_run_collection_truncated")
    observed_pr = _mapping(client.get(f"{prefix}/pulls/{pr_number}"))
    return {
        "schema": SNAPSHOT_SCHEMA,
        "repository_slug": client.repository_slug,
        "repository": {"default_branch": default_branch},
        "event": {
            "kind": event_kind,
            "delivery_id": delivery_id,
            "head_sha": expected_head_sha,
        },
        "expected_pull_request": expected_pr,
        "observed_pull_request": observed_pr,
        "reviews": reviews,
        "review_comments": comments,
        "review_threads": review_threads,
        "files": files,
        "check_runs": check_runs,
        "history": history,
        "policy": {
            "max_cycles": cycle_contract.MAX_CYCLES,
            "protected_refs": effective_protected_refs,
            "ci_checks": ci_rules,
            "speculoos_checks": speculoos_rules,
        },
    }


def resolve_event_context(
    event_name: str,
    event: dict[str, Any],
    dispatch_pr_number: str,
    dispatch_head_sha: str,
    run_id: str,
) -> dict[str, Any]:
    if event_name == "workflow_dispatch":
        try:
            pr_number = int(dispatch_pr_number)
        except (TypeError, ValueError) as exc:
            raise CoordinatorError("invalid_dispatch_pr_number") from exc
        head_sha = dispatch_head_sha
        if not run_id.isdigit() or int(run_id) < 1:
            raise CoordinatorError("invalid_run_id")
        delivery_id = f"workflow-dispatch:{run_id}"
        kind = "workflow_dispatch"
    elif event_name == "check_run":
        check_run = _mapping(event.get("check_run"))
        pull_requests = _list(check_run.get("pull_requests"))
        pr_number = _integer(_mapping(pull_requests[0]).get("number")) if len(pull_requests) == 1 else None
        head_sha = _text(check_run.get("head_sha"))
        event_id = _integer(check_run.get("id"))
        if event_id is None or event_id < 1:
            raise CoordinatorError("invalid_event_id")
        delivery_id = f"check-run:{event_id}"
        kind = "pullfrog_review_completed"
    elif event_name == "workflow_run":
        workflow_run = _mapping(event.get("workflow_run"))
        pull_requests = _list(workflow_run.get("pull_requests"))
        pr_number = _integer(_mapping(pull_requests[0]).get("number")) if len(pull_requests) == 1 else None
        head_sha = _text(workflow_run.get("head_sha"))
        event_id = _integer(workflow_run.get("id"))
        if event_id is None or event_id < 1:
            raise CoordinatorError("invalid_event_id")
        delivery_id = f"workflow-run:{event_id}"
        kind = "required_evidence_completed"
    else:
        raise CoordinatorError("unsupported_event")
    if pr_number is None or pr_number < 1 or not SHA_RE.fullmatch(head_sha):
        raise CoordinatorError("invalid_event_context")
    return {
        "pr_number": pr_number,
        "expected_head_sha": head_sha,
        "delivery_id": delivery_id,
        "event_kind": kind,
    }


def _parse_rule(value: str) -> dict[str, str]:
    if "=" not in value:
        raise CoordinatorError("invalid_check_rule")
    name, app_slug = value.rsplit("=", 1)
    rule = {"name": name, "app_slug": app_slug}
    if _check_rule(rule) is None:
        raise CoordinatorError("invalid_check_rule")
    return rule


def _write_receipt(receipt: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _failure_receipt(code: str) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "mode": MODE,
        "status": "stopped",
        "would_action": "none",
        "executed_action": "none",
        "coordinator_blockers": [code],
        "mutation": {
            "enabled": False,
            "attempted": False,
            "repository_write": False,
            "provider_invocation": False,
            "approval": False,
            "merge": False,
            "rerun": False,
            "release": False,
            "deployment": False,
            "settings_change": False,
            "branch_deletion": False,
        },
    }


def _append_github_output(path: Path, context: dict[str, Any]) -> None:
    lines = [f"{key}={value}" for key, value in context.items()]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _append_summary(path: Path, receipt: dict[str, Any]) -> None:
    blockers = list(receipt.get("coordinator_blockers") or [])
    blockers.extend(_list(_mapping(receipt.get("cycle_decision")).get("blockers")))
    lines = [
        "## Pullfrog cloud coordinator, dry run",
        "",
        f"- Status: `{receipt.get('status', 'stopped')}`",
        f"- Would action: `{receipt.get('would_action', 'none')}`",
        "- Executed action: `none`",
        "- Repository mutation: `false`",
        "- Provider invocation: `false`",
    ]
    if blockers:
        lines.extend(["", "### Fail-closed blockers"])
        lines.extend(f"- `{item}`" for item in sorted(set(_text(item) for item in blockers if _text(item))))
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve-event")
    resolve.add_argument("--event", required=True)
    resolve.add_argument("--event-name", required=True)
    resolve.add_argument("--dispatch-pr-number", default="")
    resolve.add_argument("--dispatch-head-sha", default="")
    resolve.add_argument("--run-id", required=True)
    resolve.add_argument("--github-output", required=True)
    resolve.add_argument("--failure-receipt", required=True)

    evaluate = subparsers.add_parser("evaluate-snapshot")
    evaluate.add_argument("--snapshot", required=True)
    evaluate.add_argument("--out", required=True)
    evaluate.add_argument("--fail-on-stopped", action="store_true")

    github = subparsers.add_parser("evaluate-github")
    github.add_argument("--repository", required=True)
    github.add_argument("--pr-number", required=True, type=int)
    github.add_argument("--expected-head-sha", required=True)
    github.add_argument("--event-kind", required=True)
    github.add_argument("--delivery-id", required=True)
    github.add_argument("--protected-ref", action="append", default=[])
    github.add_argument("--ci-check", action="append", default=[])
    github.add_argument("--speculoos-check", action="append", default=[])
    github.add_argument("--history")
    github.add_argument("--out", required=True)
    github.add_argument("--fail-on-stopped", action="store_true")

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--receipt", required=True)
    summarize.add_argument("--github-step-summary", required=True)
    summarize.add_argument("--fail-on-stopped", action="store_true")

    args = parser.parse_args()
    if args.command == "resolve-event":
        try:
            context = resolve_event_context(
                args.event_name,
                _load_object(Path(args.event)),
                args.dispatch_pr_number,
                args.dispatch_head_sha,
                args.run_id,
            )
        except CoordinatorError as exc:
            _write_receipt(_failure_receipt(exc.code), Path(args.failure_receipt))
            return 2
        _append_github_output(Path(args.github_output), context)
        return 0

    if args.command == "summarize":
        receipt = _load_object(Path(args.receipt))
        if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("mode") != MODE:
            raise SystemExit("invalid coordinator receipt")
        _append_summary(Path(args.github_step_summary), receipt)
        return 2 if args.fail_on_stopped and receipt.get("status") == "stopped" else 0

    out = Path(args.out)
    try:
        if args.command == "evaluate-snapshot":
            receipt = evaluate_snapshot(_load_object(Path(args.snapshot)))
        else:
            history = _validated_history(
                _load_object(Path(args.history)) if args.history else _empty_history()
            )
            snapshot = collect_github_snapshot(
                api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
                token=os.environ.get("GITHUB_TOKEN", ""),
                repository_slug=args.repository,
                pr_number=args.pr_number,
                expected_head_sha=args.expected_head_sha,
                event_kind=args.event_kind,
                delivery_id=args.delivery_id,
                protected_refs=list(args.protected_ref),
                ci_rules=[_parse_rule(item) for item in args.ci_check],
                speculoos_rules=[_parse_rule(item) for item in args.speculoos_check],
                history=history,
            )
            receipt = evaluate_snapshot(snapshot)
    except CoordinatorError as exc:
        receipt = _failure_receipt(exc.code)
    _write_receipt(receipt, out)
    print(
        f"coordinator_receipt={out} mode={MODE} status={receipt['status']} "
        f"would_action={receipt.get('would_action', 'none')} executed_action=none"
    )
    return 2 if args.fail_on_stopped and receipt["status"] == "stopped" else 0


if __name__ == "__main__":
    raise SystemExit(main())
