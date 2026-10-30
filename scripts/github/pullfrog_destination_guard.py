#!/usr/bin/env python3
"""Fail-closed destination and path guard for Pullfrog remediation.

The guard is provider-free and side-effect-free. It authorizes only the exact
current PR head in the target repository and cannot be overridden by credentials,
environment variables, or unrelated event fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

INPUT_SCHEMA = "pullfrog-destination-guard.v1"
RECEIPT_SCHEMA = "pullfrog-destination-guard-receipt.v1"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
OWNER_RE = re.compile(r"^(?=.{1,39}$)(?!-)(?!.*--)[A-Za-z0-9-]+(?<!-)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
ALLOWED_HEAD_PREFIXES = ("feat/", "fix/", "docs/", "test/", "chore/")
PROTECTED_AUTOMATION_AUTHORITY_PATHS = frozenset(
    {
        "scripts/github/pullfrog_cloud_coordinator.py",
        "scripts/github/pullfrog_cloud_remediation.py",
        "scripts/github/pullfrog_cycle_contract.py",
        "scripts/github/pullfrog_destination_guard.py",
        "scripts/github/pullfrog_dev_auto_merge.py",
        "scripts/github/pullfrog_review_fallback.py",
        "scripts/github/pullfrog_review_contract.py",
        "scripts/github/pullfrog_trusted_author_policy.json",
        "scripts/github/pullfrog_trusted_author_policy.py",
        "scripts/github/speculoos_pr_contract.py",
        "scripts/github/validate_pullfrog_workflow.sh",
        "scripts/github/tests/test_pullfrog_cloud_coordinator_workflow_policy.py",
        "scripts/github/tests/test_pullfrog_cloud_remediation_workflow_policy.py",
        "scripts/github/tests/test_pullfrog_speculoos_workflow_policy.py",
        "scripts/github/tests/test_pullfrog_review_fallback.py",
        "scripts/github/tests/test_pullfrog_review_fallback_workflow_policy.py",
        "scripts/github/tests/test_pullfrog_review_contract.py",
        "scripts/github/tests/test_pullfrog_trusted_author_policy.py",
        "scripts/github/tests/test_pullfrog_workflow_policy.py",
    }
)
FORBIDDEN_EXACT_PATHS = frozenset(
    {
        ".github/CODEOWNERS",
        ".github/dependabot.yml",
        "templates/repo-workflow-materialization-manifest.json",
        "templates/workflow-ref-sync-manifest.json",
    }
) | PROTECTED_AUTOMATION_AUTHORITY_PATHS
FORBIDDEN_PATH_PREFIXES = (
    ".github/actions/",
    ".github/workflows/",
    ".speculoos/",
    "templates/reusable-workflows/",
    "templates/starter-workflows/",
)
MAX_CHANGED_PATHS = 500
MAX_ATTEMPTS = 3


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
    if value.startswith(("-", "/", "refs/")) or value.endswith(("/", ".")):
        return False
    if value == "@" or "@{" in value or ".." in value or "//" in value:
        return False
    return all(
        component
        and not component.startswith(".")
        and not component.endswith(".lock")
        for component in value.split("/")
    )


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


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_identity(
    name: str, value: dict[str, Any], blockers: list[str]
) -> dict[str, Any]:
    slug = _canonical_slug(_text(value.get("slug")))
    head_repository = _canonical_slug(_text(value.get("head_repository_slug")))
    pr_number = value.get("pr_number")
    base_ref = _text(value.get("base_ref"))
    base_sha = _text(value.get("base_sha"))
    head_ref = _text(value.get("head_ref"))
    head_sha = _text(value.get("head_sha"))
    default_branch = _text(value.get("default_branch"))
    protected_refs_value = value.get("protected_refs")
    protected_refs = [_text(item) for item in _list(protected_refs_value)]

    if not slug:
        blockers.append(f"invalid_{name}_repository")
    if not head_repository:
        blockers.append(f"invalid_{name}_head_repository")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number < 1:
        blockers.append(f"invalid_{name}_pr_number")
    if not _valid_branch(base_ref):
        blockers.append(f"invalid_{name}_base_ref")
    if not SHA_RE.fullmatch(base_sha):
        blockers.append(f"invalid_{name}_base_sha")
    if not _valid_branch(head_ref):
        blockers.append(f"invalid_{name}_head_ref")
    if not SHA_RE.fullmatch(head_sha):
        blockers.append(f"invalid_{name}_head_sha")
    if not _valid_branch(default_branch):
        blockers.append(f"invalid_{name}_default_branch")
    if (
        not isinstance(protected_refs_value, list)
        or not protected_refs
        or any(not _valid_branch(item) for item in protected_refs)
        or len(set(protected_refs)) != len(protected_refs)
    ):
        blockers.append(f"invalid_{name}_protected_refs")
    elif base_ref not in protected_refs or default_branch not in protected_refs:
        blockers.append(f"incomplete_{name}_protected_refs")

    return {
        "slug": slug,
        "head_repository_slug": head_repository,
        "pr_number": pr_number,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "head_ref": head_ref,
        "head_sha": head_sha,
        "default_branch": default_branch,
        "protected_refs": protected_refs,
    }


def evaluate_guard(payload: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if payload.get("schema") != INPUT_SCHEMA:
        blockers.append("invalid_schema")

    expected = _validate_identity("expected", _mapping(payload.get("expected")), blockers)
    observed = _validate_identity("observed", _mapping(payload.get("observed")), blockers)

    for field in (
        "slug",
        "head_repository_slug",
        "pr_number",
        "base_ref",
        "base_sha",
        "head_ref",
        "head_sha",
        "default_branch",
        "protected_refs",
    ):
        if expected[field] != observed[field]:
            blockers.append(f"{field}_drift")

    if observed["slug"] and observed["head_repository_slug"] != observed["slug"]:
        blockers.append("fork_head_forbidden")
    if observed["head_ref"] and not observed["head_ref"].startswith(ALLOWED_HEAD_PREFIXES):
        blockers.append("head_prefix_forbidden")
    if observed["head_ref"] in observed["protected_refs"]:
        blockers.append("protected_head_forbidden")
    if observed["head_ref"] in {observed["base_ref"], observed["default_branch"]}:
        blockers.append("base_or_default_head_forbidden")
    if observed["base_sha"] and observed["base_sha"] == observed["head_sha"]:
        blockers.append("base_head_sha_match")

    request = _mapping(payload.get("request"))
    destination_slug = _canonical_slug(_text(request.get("destination_repository_slug")))
    destination_ref = _text(request.get("destination_ref"))
    destination_sha = _text(request.get("destination_sha"))
    changed_paths_value = request.get("changed_paths")
    changed_paths = [_text(item) for item in _list(changed_paths_value)]
    attempt = request.get("attempt")

    if not destination_slug:
        blockers.append("invalid_destination_repository")
    if not _valid_branch(destination_ref):
        blockers.append("invalid_destination_ref")
    if not SHA_RE.fullmatch(destination_sha):
        blockers.append("invalid_destination_sha")
    if destination_slug != observed["slug"]:
        blockers.append("destination_repository_mismatch")
    if destination_ref != observed["head_ref"]:
        blockers.append("destination_ref_mismatch")
    if destination_sha != observed["head_sha"]:
        blockers.append("destination_sha_mismatch")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or not 1 <= attempt <= MAX_ATTEMPTS:
        blockers.append("invalid_attempt")
    if (
        not isinstance(changed_paths_value, list)
        or not changed_paths
        or len(changed_paths) > MAX_CHANGED_PATHS
        or any(not _valid_path(path) for path in changed_paths)
        or len(set(changed_paths)) != len(changed_paths)
    ):
        blockers.append("invalid_changed_paths")

    forbidden_paths = sorted(
        path
        for path in set(changed_paths)
        if path in FORBIDDEN_EXACT_PATHS
        or any(path.startswith(prefix) for prefix in FORBIDDEN_PATH_PREFIXES)
    )
    if forbidden_paths:
        blockers.append("forbidden_changed_path")

    first = _mapping(payload.get("first_attempt"))
    first_slug = _canonical_slug(_text(first.get("destination_repository_slug")))
    first_ref = _text(first.get("destination_ref"))
    first_sha = _text(first.get("destination_sha"))
    if not first_slug or not _valid_branch(first_ref) or not SHA_RE.fullmatch(first_sha):
        blockers.append("invalid_first_attempt_destination")
    if first_slug != destination_slug or first_ref != destination_ref or first_sha != destination_sha:
        blockers.append("retry_destination_changed")
    if first_slug != observed["slug"] or first_ref != observed["head_ref"] or first_sha != observed["head_sha"]:
        blockers.append("first_attempt_destination_mismatch")

    blockers = sorted(set(blockers))
    status = "allowed" if not blockers else "blocked"
    sanitized_payload = dict(payload)
    sanitized_payload.pop("notes", None)
    return {
        "schema": RECEIPT_SCHEMA,
        "input_digest": _digest(sanitized_payload),
        "status": status,
        "blockers": blockers,
        "destination": {
            "repository_slug": destination_slug,
            "ref": destination_ref,
            "sha": destination_sha,
            "attempt": attempt,
        },
        "policy": {
            "forks_allowed": False,
            "allowed_head_prefixes": list(ALLOWED_HEAD_PREFIXES),
            "max_attempts": MAX_ATTEMPTS,
            "forbidden_exact_paths": sorted(FORBIDDEN_EXACT_PATHS),
            "forbidden_path_prefixes": list(FORBIDDEN_PATH_PREFIXES),
        },
        "paths": {
            "count": len(changed_paths),
            "digest": _digest(sorted(changed_paths)),
            "forbidden": forbidden_paths,
        },
    }


def _load_payload(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("guard payload root must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    try:
        receipt = evaluate_guard(_load_payload(Path(args.payload)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"destination guard validation failed: {exc}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"destination_guard={out} status={receipt['status']}")
    return 2 if args.fail_on_blocked and receipt["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
