#!/usr/bin/env python3
"""Evaluate one exact-head Pullfrog review/remediation cycle.

This module is deliberately provider-free and side-effect-free. A GitHub Actions
coordinator can feed it a bounded observation and act only on the returned
machine-checkable decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

STATE_SCHEMA = "pullfrog-cycle-state.v1"
DECISION_SCHEMA = "pullfrog-cycle-decision.v1"
MAX_CYCLES = 3
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
OWNER_RE = re.compile(r"^(?=.{1,39}$)(?!-)(?!.*--)[A-Za-z0-9-]+(?<!-)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
DELIVERY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
REVIEW_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
ALLOWED_EVENT_KINDS = {
    "pullfrog_review_completed",
    "pull_request_synchronize",
    "required_evidence_completed",
    "workflow_dispatch",
}
ALLOWED_REVIEW_STATUSES = {
    "success",
    "failure",
    "pending",
    "cancelled",
    "timed_out",
    "missing",
}
ALLOWED_CHECK_STATUSES = {
    "success",
    "failure",
    "pending",
    "cancelled",
    "timed_out",
    "missing",
    "skipped",
}
ALLOWED_SEVERITIES = {"blocker", "high", "medium", "low", "info"}
ALWAYS_SUCCESS_CHECKS = frozenset({"pullfrog", "ci", "speculoos", "destination-guard"})
APPROVAL_CHECK = "pullfrog-approval"
REQUIRED_CHECKS = ALWAYS_SUCCESS_CHECKS | {APPROVAL_CHECK}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _canonical_slug(value: str) -> str:
    if value.count("/") != 1:
        return ""
    owner, repository = value.split("/", 1)
    if not OWNER_RE.fullmatch(owner):
        return ""
    if not REPOSITORY_RE.fullmatch(repository) or repository in {".", ".."}:
        return ""
    return f"{owner.casefold()}/{repository.casefold()}"


def _valid_branch(value: str) -> bool:
    if not value or not BRANCH_RE.fullmatch(value):
        return False
    if value.startswith(("-", "/")) or value.endswith(("/", ".")):
        return False
    if value == "@" or "@{" in value or ".." in value or "//" in value:
        return False
    return all(
        component
        and not component.startswith(".")
        and not component.endswith(".lock")
        for component in value.split("/")
    )


def _valid_relative_path(value: str) -> bool:
    if not value or "\\" in value or value.startswith("/"):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _canonical_claim(value: str) -> str:
    parts = value.rsplit(":", 3)
    if len(parts) != 4:
        return ""
    slug, pr_text, head_sha, cycle_text = parts
    canonical_slug = _canonical_slug(slug)
    if not canonical_slug or not SHA_RE.fullmatch(head_sha):
        return ""
    if not pr_text.isdigit() or not cycle_text.isdigit():
        return ""
    pr_number = int(pr_text)
    cycle = int(cycle_text)
    if pr_number < 1 or not 0 <= cycle <= MAX_CYCLES:
        return ""
    return f"{canonical_slug}:{pr_number}:{head_sha}:{cycle}"


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_summary(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalize_findings(value: Any, blockers: list[str]) -> tuple[list[str], str]:
    if not isinstance(value, list):
        blockers.append("invalid_findings")
        return [], _canonical_digest([])

    fingerprints: list[str] = []
    for finding in value:
        item = _mapping(finding)
        finding_id = _text(item.get("id"))
        severity = _text(item.get("severity"))
        path = _text(item.get("path"))
        line = item.get("line")
        summary = _text(item.get("summary"))
        if (
            (finding_id and len(finding_id) > 100)
            or severity not in ALLOWED_SEVERITIES
            or not _valid_relative_path(path)
            or not isinstance(line, int)
            or isinstance(line, bool)
            or line < 1
            or not summary
            or len(summary) > 500
        ):
            blockers.append("invalid_finding")
            continue
        normalized = {
            "id": finding_id.casefold(),
            "severity": severity,
            "path": path,
            "line": line,
            "summary": _normalized_summary(summary),
        }
        fingerprints.append(_canonical_digest(normalized))

    if len(set(fingerprints)) != len(fingerprints):
        blockers.append("duplicate_finding")
    fingerprints = sorted(set(fingerprints))
    return fingerprints, _canonical_digest(fingerprints)


def _validate_expected_observed(
    expected: dict[str, Any], observed: dict[str, Any], blockers: list[str]
) -> tuple[str, int, str]:
    expected_slug = _canonical_slug(_text(expected.get("slug")))
    observed_slug = _canonical_slug(_text(observed.get("slug")))
    expected_head_repository = _canonical_slug(_text(expected.get("head_repository_slug")))
    observed_head_repository = _canonical_slug(_text(observed.get("head_repository_slug")))
    expected_pr = expected.get("pr_number")
    observed_pr = observed.get("pr_number")

    for prefix, slug, pr_number, head_repository in (
        ("expected", expected_slug, expected_pr, expected_head_repository),
        ("observed", observed_slug, observed_pr, observed_head_repository),
    ):
        if not slug:
            blockers.append(f"invalid_{prefix}_repository")
        if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number < 1:
            blockers.append(f"invalid_{prefix}_pr_number")
        if not head_repository:
            blockers.append(f"invalid_{prefix}_head_repository")
        for field in ("base_sha", "head_sha"):
            if not SHA_RE.fullmatch(_text((expected if prefix == "expected" else observed).get(field))):
                blockers.append(f"invalid_{prefix}_{field}")
        for field in ("base_ref", "head_ref"):
            if not _valid_branch(_text((expected if prefix == "expected" else observed).get(field))):
                blockers.append(f"invalid_{prefix}_{field}")

    comparisons = {
        "repository_drift": expected_slug != observed_slug,
        "pr_drift": expected_pr != observed_pr,
        "base_ref_drift": _text(expected.get("base_ref")) != _text(observed.get("base_ref")),
        "base_sha_drift": _text(expected.get("base_sha")) != _text(observed.get("base_sha")),
        "head_ref_drift": _text(expected.get("head_ref")) != _text(observed.get("head_ref")),
        "head_sha_drift": _text(expected.get("head_sha")) != _text(observed.get("head_sha")),
        "head_repository_drift": expected_head_repository != observed_head_repository,
    }
    blockers.extend(name for name, drifted in comparisons.items() if drifted)
    if (
        SHA_RE.fullmatch(_text(observed.get("base_sha")))
        and _text(observed.get("base_sha")) == _text(observed.get("head_sha"))
    ):
        blockers.append("base_head_sha_match")
    return observed_slug, observed_pr if isinstance(observed_pr, int) else 0, _text(observed.get("head_sha"))


def evaluate_state(state: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if state.get("schema") != STATE_SCHEMA:
        blockers.append("invalid_schema")

    expected = _mapping(state.get("expected"))
    observed = _mapping(state.get("observed"))
    slug, pr_number, head_sha = _validate_expected_observed(expected, observed, blockers)

    event = _mapping(state.get("event"))
    delivery_id = _text(event.get("delivery_id"))
    event_kind = _text(event.get("kind"))
    event_head_sha = _text(event.get("head_sha"))
    if not DELIVERY_RE.fullmatch(delivery_id):
        blockers.append("invalid_delivery_id")
    if event_kind not in ALLOWED_EVENT_KINDS:
        blockers.append("invalid_event_kind")
    if not SHA_RE.fullmatch(event_head_sha):
        blockers.append("invalid_event_head_sha")
    elif event_head_sha != head_sha:
        blockers.append("stale_event_head")

    policy = _mapping(state.get("policy"))
    max_cycles = policy.get("max_cycles")
    if (
        not isinstance(max_cycles, int)
        or isinstance(max_cycles, bool)
        or not 1 <= max_cycles <= MAX_CYCLES
    ):
        blockers.append("invalid_max_cycles")

    cycle = _mapping(state.get("cycle"))
    cycle_number = cycle.get("number")
    claim_key = _text(cycle.get("claim_key"))
    if (
        not isinstance(cycle_number, int)
        or isinstance(cycle_number, bool)
        or cycle_number < 0
        or cycle_number > MAX_CYCLES
    ):
        blockers.append("invalid_cycle")
        cycle_number = -1
    expected_claim = f"{slug}:{pr_number}:{head_sha}:{cycle_number}"
    canonical_claim = _canonical_claim(claim_key)
    if not canonical_claim or canonical_claim != expected_claim:
        blockers.append("invalid_claim_key")

    history = _mapping(state.get("history"))
    completed_claim_values = history.get("completed_claim_keys")
    source_head_values = history.get("remediation_source_heads")
    finding_digest_values = history.get("finding_set_digests")
    output_digest_values = history.get("output_digests")
    history_lists = {
        "completed_claim_keys": completed_claim_values,
        "remediation_source_heads": source_head_values,
        "finding_set_digests": finding_digest_values,
        "output_digests": output_digest_values,
    }
    for name, value in history_lists.items():
        if not isinstance(value, list):
            blockers.append(f"invalid_history_{name}")

    completed_claims = [_canonical_claim(_text(item)) for item in _list(completed_claim_values)]
    source_heads = [_text(item) for item in _list(source_head_values)]
    prior_finding_digests = [_text(item) for item in _list(finding_digest_values)]
    prior_output_digests = [_text(item) for item in _list(output_digest_values)]
    if any(not item for item in completed_claims) or len(set(completed_claims)) != len(completed_claims):
        blockers.append("invalid_completed_claim_history")
    if any(not SHA_RE.fullmatch(item) for item in source_heads) or len(set(source_heads)) != len(source_heads):
        blockers.append("invalid_source_head_history")
    if (
        any(not DIGEST_RE.fullmatch(item) for item in prior_finding_digests)
        or len(set(prior_finding_digests)) != len(prior_finding_digests)
    ):
        blockers.append("invalid_finding_digest_history")
    if (
        any(not DIGEST_RE.fullmatch(item) for item in prior_output_digests)
        or len(set(prior_output_digests)) != len(prior_output_digests)
    ):
        blockers.append("invalid_output_digest_history")
    if cycle_number >= 0 and not (
        len(source_heads) == len(prior_finding_digests) == len(prior_output_digests) == cycle_number
    ):
        blockers.append("incomplete_cycle_history")

    duplicate = bool(canonical_claim and canonical_claim in completed_claims)
    if cycle_number > 0 and source_heads and source_heads[-1] == head_sha:
        blockers.append("unchanged_head")
    if head_sha in source_heads:
        blockers.append("reused_head")

    review = _mapping(state.get("review"))
    review_status = _text(review.get("status"))
    review_head_sha = _text(review.get("head_sha"))
    review_id = _text(review.get("review_id"))
    output_digest = _text(review.get("output_digest"))
    if review_status not in ALLOWED_REVIEW_STATUSES:
        blockers.append("invalid_review_status")
    elif review_status != "success":
        blockers.append(f"review_{review_status}")
    if not SHA_RE.fullmatch(review_head_sha):
        blockers.append("invalid_review_head_sha")
    elif review_head_sha != head_sha:
        blockers.append("stale_review_head")
    if not REVIEW_ID_RE.fullmatch(review_id):
        blockers.append("invalid_review_id")
    if not DIGEST_RE.fullmatch(output_digest):
        blockers.append("invalid_output_digest")

    fingerprints, finding_set_digest = _normalize_findings(review.get("findings"), blockers)
    finding_count = len(fingerprints)
    if cycle_number > 0 and finding_set_digest in prior_finding_digests:
        blockers.append("repeated_findings")
    if cycle_number > 0 and output_digest in prior_output_digests:
        blockers.append("unchanged_output")

    checks_value = state.get("checks")
    checks = _list(checks_value)
    if not isinstance(checks_value, list) or not checks:
        blockers.append("missing_checks")
    check_map: dict[str, dict[str, Any]] = {}
    for check in checks:
        item = _mapping(check)
        name = _text(item.get("name"))
        status = _text(item.get("status"))
        check_head_sha = _text(item.get("head_sha"))
        if not name or name in check_map:
            blockers.append("invalid_check_identity")
            continue
        if status not in ALLOWED_CHECK_STATUSES:
            blockers.append("invalid_check_status")
        if not SHA_RE.fullmatch(check_head_sha):
            blockers.append("invalid_check_head_sha")
        elif check_head_sha != head_sha:
            blockers.append("stale_check_head")
        check_map[name] = {"status": status, "head_sha": check_head_sha}

    missing_checks = sorted(REQUIRED_CHECKS - set(check_map))
    if missing_checks:
        blockers.append("missing_required_check")
    for name in ALWAYS_SUCCESS_CHECKS:
        if name in check_map and check_map[name]["status"] != "success":
            blockers.append(f"check_{name}_{check_map[name]['status']}")
    if APPROVAL_CHECK in check_map:
        approval_status = check_map[APPROVAL_CHECK]["status"]
        expected_approval = "failure" if finding_count else "success"
        if approval_status != expected_approval:
            blockers.append("inconsistent_pullfrog_approval")

    if isinstance(max_cycles, int) and cycle_number >= max_cycles and finding_count:
        blockers.append("cycle_limit_exhausted")

    blockers = sorted(set(blockers))
    if duplicate and not [item for item in blockers if item not in {"unchanged_head", "reused_head"}]:
        status = "duplicate"
        action = "none"
        blockers = []
    elif blockers:
        status = "stopped"
        action = "none"
    elif finding_count:
        status = "remediation_ready"
        action = "start_remediation"
    else:
        status = "clean"
        action = "complete"

    sanitized_input = dict(state)
    sanitized_input.pop("notes", None)
    return {
        "schema": DECISION_SCHEMA,
        "input_digest": _canonical_digest(sanitized_input),
        "status": status,
        "action": action,
        "blockers": blockers,
        "duplicate": duplicate,
        "repository": {
            "slug": slug,
            "pr_number": pr_number,
            "base_ref": _text(observed.get("base_ref")),
            "base_sha": _text(observed.get("base_sha")),
            "head_ref": _text(observed.get("head_ref")),
            "head_sha": head_sha,
            "head_repository_slug": _canonical_slug(_text(observed.get("head_repository_slug"))),
        },
        "event": {
            "delivery_id": delivery_id,
            "kind": event_kind,
            "head_sha": event_head_sha,
        },
        "cycle": {
            "number": cycle_number,
            "max_cycles": max_cycles,
            "next_number": cycle_number + 1 if action == "start_remediation" else None,
            "claim_key": canonical_claim,
        },
        "review": {
            "review_id": review_id,
            "head_sha": review_head_sha,
            "finding_count": finding_count,
            "finding_fingerprints": fingerprints,
            "finding_set_digest": finding_set_digest,
            "output_digest": output_digest,
        },
        "evidence": {
            "required_checks": sorted(REQUIRED_CHECKS),
            "missing_checks": missing_checks,
            "observed_checks": {
                name: check_map[name] for name in sorted(check_map) if name in REQUIRED_CHECKS
            },
        },
    }


def _load_state(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("state root must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fail-on-stopped", action="store_true")
    args = parser.parse_args()

    try:
        decision = evaluate_state(_load_state(Path(args.state)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cycle state validation failed: {exc}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"cycle_decision={out} status={decision['status']} action={decision['action']}")
    return 2 if args.fail_on_stopped and decision["status"] == "stopped" else 0


if __name__ == "__main__":
    raise SystemExit(main())
