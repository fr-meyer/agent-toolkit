#!/usr/bin/env python3
"""Evaluate a provider-free, non-merge PR automation dogfood scenario.

The evaluator deliberately performs no network, provider, Git, or GitHub writes.
It emits a deterministic, sanitized receipt suitable for CI fixtures.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

SCENARIO_SCHEMA = "pr-automation-dogfood.v1"
RECEIPT_SCHEMA = "pr-automation-dogfood-receipt.v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BRANCH_ALLOWED_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
ACTOR_LOGIN_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?$"
)
CLAIM_KEY_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:[0-9a-f]{40}:[1-9][0-9]*$"
)
PROTECTED_HEAD_REFS = {"dev", "main", "master"}
ALLOWED_WRITE_SCOPES = {"none", "fixture-only"}
REQUIRED_CHECK_NAMES = frozenset({"dogfood-contract", "unit-tests"})


def _mapping(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _valid_branch_ref(value: str) -> bool:
    """Apply the relevant fail-closed `git check-ref-format --branch` rules."""
    if not value or not BRANCH_ALLOWED_RE.fullmatch(value):
        return False
    if value.startswith(("-", "/")) or value.endswith(("/", ".")):
        return False
    if value == "@" or "@{" in value or ".." in value or "//" in value:
        return False
    components = value.split("/")
    return all(
        component
        and not component.startswith(".")
        and not component.endswith(".lock")
        for component in components
    )


def _canonical_actor_login(value: str) -> str:
    """Return a normalized GitHub actor label, or empty text when malformed."""
    if not ACTOR_LOGIN_RE.fullmatch(value):
        return ""
    return value.casefold()


def _valid_claim_key(value: str) -> bool:
    """Accept only the canonical repository:head-sha:cycle claim-key shape."""
    if not CLAIM_KEY_RE.fullmatch(value):
        return False
    slug, _head_sha, cycle_text = value.rsplit(":", 2)
    slug_parts = slug.split("/", 1)
    return all(part not in {".", ".."} for part in slug_parts) and int(cycle_text) <= 2


def _canonical_digest(scenario: Dict[str, Any]) -> str:
    payload = dict(scenario)
    payload.pop("expected", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []

    if scenario.get("schema") != SCENARIO_SCHEMA:
        blockers.append("invalid_schema")

    repository = _mapping(scenario.get("repository"))
    slug = _text(repository.get("slug"))
    base_ref = _text(repository.get("base_ref"))
    base_sha = _text(repository.get("base_sha"))
    head_ref = _text(repository.get("head_ref"))
    head_sha = _text(repository.get("head_sha"))

    slug_parts = slug.split("/", 1)
    if not SLUG_RE.fullmatch(slug) or any(part in {".", ".."} for part in slug_parts):
        blockers.append("invalid_repository_slug")
    if base_ref != "dev":
        blockers.append("invalid_base_ref")
    if not SHA_RE.fullmatch(base_sha):
        blockers.append("invalid_base_sha")
    if not _valid_branch_ref(head_ref):
        blockers.append("invalid_head_ref")
    protected_head = head_ref.removeprefix("refs/heads/")
    if protected_head in PROTECTED_HEAD_REFS:
        blockers.append("protected_head_ref")
    if not SHA_RE.fullmatch(head_sha):
        blockers.append("invalid_head_sha")
    if base_sha and head_sha and base_sha == head_sha:
        blockers.append("base_head_sha_match")

    actors = _mapping(scenario.get("actors"))
    author_login = _text(actors.get("author_login"))
    reviewer_login = _text(actors.get("reviewer_login"))
    canonical_author_login = _canonical_actor_login(author_login)
    canonical_reviewer_login = _canonical_actor_login(reviewer_login)
    if not author_login or not reviewer_login:
        blockers.append("missing_actor_identity")
    elif not canonical_author_login or not canonical_reviewer_login:
        blockers.append("invalid_actor_identity")
    elif canonical_author_login == canonical_reviewer_login:
        blockers.append("actor_identity_overlap")

    run = _mapping(scenario.get("run"))
    cycle = run.get("cycle")
    max_cycles = run.get("max_cycles")
    claim_key = _text(run.get("claim_key"))
    prior_claim_keys_value = run.get("prior_claim_keys")
    prior_claim_keys: List[str] = []
    claim_history_valid = False
    if "prior_claim_keys" not in run:
        blockers.append("missing_claim_history")
    elif not isinstance(prior_claim_keys_value, list):
        blockers.append("invalid_claim_history")
    else:
        prior_claim_keys = [_text(item) for item in prior_claim_keys_value]
        claim_history_valid = (
            all(_valid_claim_key(item) for item in prior_claim_keys)
            and len(set(prior_claim_keys)) == len(prior_claim_keys)
        )
        if not claim_history_valid:
            blockers.append("invalid_claim_history")

    if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 1:
        blockers.append("invalid_cycle")
    if not isinstance(max_cycles, int) or isinstance(max_cycles, bool) or not 1 <= max_cycles <= 2:
        blockers.append("invalid_max_cycles")
    if isinstance(cycle, int) and isinstance(max_cycles, int) and cycle > max_cycles:
        blockers.append("cycle_limit_exceeded")

    expected_claim_key = "{}:{}:{}".format(slug, head_sha, cycle)
    if not claim_key or claim_key != expected_claim_key:
        blockers.append("invalid_claim_key")
    if claim_key and claim_key in prior_claim_keys:
        blockers.append("duplicate_claim")

    evidence = _mapping(scenario.get("evidence"))
    reviewed_head_sha = _text(evidence.get("reviewed_head_sha"))
    if not SHA_RE.fullmatch(reviewed_head_sha):
        blockers.append("invalid_reviewed_head_sha")
    elif reviewed_head_sha != head_sha:
        blockers.append("stale_review_head")

    checks = _list(evidence.get("required_checks"))
    check_names: List[str] = []
    missing_required_check_names = set(REQUIRED_CHECK_NAMES)
    unexpected_required_check_names = set()
    check_names_valid = False
    if not checks:
        blockers.append("missing_required_checks")
    else:
        check_names = [_text(_mapping(check).get("name")) for check in checks]
        check_names_valid = (
            bool(check_names)
            and all(check_names)
            and len(set(check_names)) == len(check_names)
        )
        if not check_names_valid:
            blockers.append("invalid_required_check")
        missing_required_check_names = REQUIRED_CHECK_NAMES - set(check_names)
        if missing_required_check_names:
            blockers.append("missing_required_check")
        unexpected_required_check_names = set(check_names) - REQUIRED_CHECK_NAMES
        if unexpected_required_check_names:
            blockers.append("unexpected_required_check")
        if any(_text(_mapping(check).get("status")) != "success" for check in checks):
            blockers.append("required_check_not_success")

    policy = _mapping(scenario.get("policy"))
    provider_calls = policy.get("provider_calls")
    secrets_exposed = policy.get("secrets_exposed")
    write_scope = _text(policy.get("write_scope"))
    merge_mode = _text(policy.get("merge_mode"))
    auto_merge = policy.get("auto_merge")

    if provider_calls is not False:
        blockers.append("provider_call_forbidden")
    if secrets_exposed is not False:
        blockers.append("secret_exposure_forbidden")
    if write_scope not in ALLOWED_WRITE_SCOPES:
        blockers.append("unsafe_write_scope")
    if merge_mode != "human":
        blockers.append("nonhuman_merge_mode")
    if auto_merge is not False:
        blockers.append("auto_merge_forbidden")

    blockers = sorted(set(blockers))
    status = "ready_for_human_merge" if not blockers else "blocked"
    checks_green = (
        bool(checks)
        and check_names_valid
        and not missing_required_check_names
        and not unexpected_required_check_names
        and all(_text(_mapping(check).get("status")) == "success" for check in checks)
    )

    return {
        "schema": RECEIPT_SCHEMA,
        "input_digest": _canonical_digest(scenario),
        "status": status,
        "blockers": blockers,
        "repository": {
            "slug": slug,
            "base_ref": base_ref,
            "base_sha": base_sha,
            "head_ref": head_ref,
            "head_sha": head_sha,
        },
        "actors": {
            "author_login": author_login,
            "reviewer_login": reviewer_login,
            "separated": bool(canonical_author_login and canonical_reviewer_login)
            and canonical_author_login != canonical_reviewer_login,
        },
        "run": {
            "cycle": cycle,
            "max_cycles": max_cycles,
            "claim_key": claim_key,
            "claim_history_valid": claim_history_valid,
            "duplicate": bool(claim_key and claim_key in prior_claim_keys),
        },
        "evidence": {
            "reviewed_head_sha": reviewed_head_sha,
            "reviewed_head_matches": bool(reviewed_head_sha and reviewed_head_sha == head_sha),
            "checks_green": checks_green,
            "required_check_names": sorted(REQUIRED_CHECK_NAMES),
            "observed_check_names": sorted(set(check_names)),
            "missing_required_check_names": sorted(missing_required_check_names),
            "unexpected_required_check_names": sorted(unexpected_required_check_names),
        },
        "policy": {
            "provider_free": provider_calls is False,
            "secrets_exposed": secrets_exposed,
            "write_scope": write_scope,
            "merge_mode": merge_mode,
            "auto_merge": auto_merge,
        },
    }


def _load_scenario(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("scenario root must be an object")
    return value


def _verify_expectation(scenario: Dict[str, Any], receipt: Dict[str, Any]) -> None:
    expected = _mapping(scenario.get("expected"))
    expected_status = _text(expected.get("status"))
    expected_blockers = sorted({_text(item) for item in _list(expected.get("blockers")) if _text(item)})
    if expected_status and receipt["status"] != expected_status:
        raise ValueError("receipt status did not match fixture expectation")
    if "blockers" in expected and receipt["blockers"] != expected_blockers:
        raise ValueError("receipt blockers did not match fixture expectation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        scenario = _load_scenario(Path(args.scenario))
        receipt = evaluate_scenario(scenario)
        _verify_expectation(scenario, receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit("dogfood scenario validation failed: {}".format(exc))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("dogfood_receipt={} status={} blockers={}".format(out_path, receipt["status"], len(receipt["blockers"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
