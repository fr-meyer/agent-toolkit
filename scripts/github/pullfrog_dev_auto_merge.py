#!/usr/bin/env python3
"""Fail-closed exact-head auto-merge for clean feature PRs targeting dev only."""

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
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pullfrog_cloud_coordinator as coordinator  # noqa: E402
import pullfrog_cycle_contract as cycle_contract  # noqa: E402

RECEIPT_SCHEMA = "pullfrog-dev-auto-merge-receipt.v1"
COORDINATOR_SCHEMA = "pullfrog-cloud-coordinator-receipt.v1"
ALLOWED_BASE_REF = "dev"
FORBIDDEN_BASE_REFS = frozenset({"main", "master"})
ALLOWED_HEAD_PREFIXES = ("feat/", "fix/", "docs/", "test/", "chore/")
REQUIRED_CHECKS = frozenset(
    {"pullfrog", "pullfrog-approval", "ci", "speculoos", "destination-guard"}
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CROSS_REPO_DISPATCH_WORKFLOW = "cross-repo-workflow-updater-manual-trigger.yml"
REF_SYNC_DISPATCH_WORKFLOW = "sync-starter-workflow-template-refs-trigger.yml"
ALLOWED_DISPATCH_WORKFLOWS = frozenset(
    {CROSS_REPO_DISPATCH_WORKFLOW, REF_SYNC_DISPATCH_WORKFLOW}
)
CROSS_REPO_TRIGGER_PATHS = frozenset(
    {
        "templates/cross-repo-workflow-distribution-manifest.json",
        "scripts/github/cross_repo_workflow_updater.py",
    }
)
REF_SYNC_TRIGGER_PATHS = frozenset(
    {
        "templates/reusable-workflows/coderabbit-pr-automation.yml",
        "templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml",
        "templates/workflow-ref-sync-manifest.json",
    }
)


class AutoMergeError(Exception):
    """Sanitized fail-closed error with a stable code."""

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


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutoMergeError("invalid_json_file") from exc
    if not isinstance(value, dict):
        raise AutoMergeError("invalid_json_root")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validated_identity(value: Any) -> dict[str, Any]:
    identity = _mapping(value)
    repository_slug = cycle_contract._canonical_slug(_text(identity.get("repository_slug")))
    head_repository_slug = cycle_contract._canonical_slug(
        _text(identity.get("head_repository_slug"))
    )
    pr_number = _integer(identity.get("pr_number"))
    base_ref = _text(identity.get("base_ref"))
    base_sha = _text(identity.get("base_sha"))
    head_ref = _text(identity.get("head_ref"))
    head_sha = _text(identity.get("head_sha"))
    if (
        not repository_slug
        or head_repository_slug != repository_slug
        or pr_number is None
        or pr_number < 1
        or base_ref != ALLOWED_BASE_REF
        or base_ref in FORBIDDEN_BASE_REFS
        or not any(
            head_ref.startswith(prefix) and len(head_ref) > len(prefix)
            for prefix in ALLOWED_HEAD_PREFIXES
        )
        or not SHA_RE.fullmatch(base_sha)
        or not SHA_RE.fullmatch(head_sha)
    ):
        raise AutoMergeError("ineligible_identity")
    return {
        "repository_slug": repository_slug,
        "pr_number": pr_number,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "head_ref": head_ref,
        "head_sha": head_sha,
        "head_repository_slug": head_repository_slug,
    }


def validate_clean_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if (
        receipt.get("schema") != COORDINATOR_SCHEMA
        or receipt.get("mode") != "dry-run"
        or receipt.get("status") != "clean"
        or receipt.get("would_action") != "complete"
        or receipt.get("executed_action") != "none"
        or receipt.get("coordinator_blockers") != []
    ):
        raise AutoMergeError("coordinator_not_clean")
    mutation = _mapping(receipt.get("mutation"))
    if mutation.get("enabled") is not False or any(
        bool(value) for key, value in mutation.items() if key != "enabled"
    ):
        raise AutoMergeError("coordinator_mutation_detected")

    identity = _validated_identity(receipt.get("identity"))
    decision = _mapping(receipt.get("cycle_decision"))
    repository = _mapping(decision.get("repository"))
    review = _mapping(decision.get("review"))
    evidence = _mapping(decision.get("evidence"))
    observed_checks = _mapping(evidence.get("observed_checks"))
    required_checks = evidence.get("required_checks")
    event = _mapping(decision.get("event"))
    if (
        decision.get("schema") != cycle_contract.DECISION_SCHEMA
        or decision.get("status") != "clean"
        or decision.get("action") != "complete"
        or decision.get("blockers") != []
        or repository.get("slug") != identity["repository_slug"]
        or repository.get("pr_number") != identity["pr_number"]
        or repository.get("base_ref") != identity["base_ref"]
        or repository.get("base_sha") != identity["base_sha"]
        or repository.get("head_ref") != identity["head_ref"]
        or repository.get("head_sha") != identity["head_sha"]
        or repository.get("head_repository_slug") != identity["head_repository_slug"]
        or _mapping(receipt.get("identity")).get("event_head_sha") != identity["head_sha"]
        or event.get("head_sha") != identity["head_sha"]
        or review.get("head_sha") != identity["head_sha"]
        or _integer(review.get("finding_count")) != 0
        or required_checks != sorted(REQUIRED_CHECKS)
        or set(observed_checks) != REQUIRED_CHECKS
        or evidence.get("missing_checks") != []
    ):
        raise AutoMergeError("invalid_clean_decision")
    for name in REQUIRED_CHECKS:
        check = _mapping(observed_checks.get(name))
        if check.get("status") != "success" or check.get("head_sha") != identity["head_sha"]:
            raise AutoMergeError("required_evidence_not_successful")

    destination = _mapping(receipt.get("destination_guard"))
    if (
        destination.get("status") != "allowed"
        or destination.get("blockers") != []
        or _text(_mapping(destination.get("destination")).get("repository_slug"))
        != identity["repository_slug"]
        or _text(_mapping(destination.get("destination")).get("ref")) != identity["head_ref"]
        or _text(_mapping(destination.get("destination")).get("sha")) != identity["head_sha"]
    ):
        raise AutoMergeError("destination_not_allowed")
    return identity


def _latest_human_verdicts(reviews: list[Any]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for value in reviews:
        review = _mapping(value)
        user = _mapping(review.get("user"))
        login = _text(user.get("login"))
        if not login or login.casefold() in {"pullfrog", "pullfrog[bot]"}:
            continue
        state = _text(review.get("state")).upper()
        if state in {"APPROVED", "CHANGES_REQUESTED"}:
            latest[login.casefold()] = state
        elif state == "DISMISSED":
            latest.pop(login.casefold(), None)
    return latest


class GitHubMergeClient(coordinator.GitHubReadClient):
    """Bounded GitHub client with one exact merge mutation."""

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        parsed_path = urllib.parse.urlparse(path)
        if (
            parsed_path.scheme
            or parsed_path.netloc
            or path != f"{self.allowed_prefix}/pulls/{payload.get('pull_number')}/merge"
        ):
            raise AutoMergeError("forbidden_github_api_path")
        body = json.dumps(
            {key: value for key, value in payload.items() if key != "pull_number"},
            separators=(",", ":"),
        ).encode("utf-8")
        request = urllib.request.Request(
            self.api_url + path,
            data=body,
            method="PUT",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "agent-toolkit-pullfrog-dev-auto-merge",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise AutoMergeError("github_merge_failed") from exc
        if len(data) > MAX_RESPONSE_BYTES:
            raise AutoMergeError("github_api_response_too_large")
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AutoMergeError("invalid_github_api_response") from exc
        if not isinstance(value, dict):
            raise AutoMergeError("invalid_github_api_response")
        return value

    def merge_exact_head(self, identity: dict[str, Any], title: str) -> dict[str, Any]:
        path = f"{self.allowed_prefix}/pulls/{identity['pr_number']}/merge"
        return self._post(
            path,
            {
                "pull_number": identity["pr_number"],
                "sha": identity["head_sha"],
                "merge_method": "merge",
                "commit_title": f"{title} (#{identity['pr_number']})",
            },
        )

    def dispatch_workflow(
        self,
        workflow: str,
        *,
        ref: str,
        inputs: dict[str, str],
    ) -> None:
        if workflow not in ALLOWED_DISPATCH_WORKFLOWS or ref != ALLOWED_BASE_REF:
            raise AutoMergeError("forbidden_workflow_dispatch")
        encoded_workflow = urllib.parse.quote(workflow, safe="")
        path = f"{self.allowed_prefix}/actions/workflows/{encoded_workflow}/dispatches"
        body = json.dumps(
            {"ref": ref, "inputs": inputs}, separators=(",", ":")
        ).encode("utf-8")
        request = urllib.request.Request(
            self.api_url + path,
            data=body,
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "agent-toolkit-pullfrog-dev-auto-merge",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 204:
                    raise AutoMergeError("workflow_dispatch_failed")
                if response.read(1):
                    raise AutoMergeError("invalid_workflow_dispatch_response")
        except AutoMergeError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise AutoMergeError("workflow_dispatch_failed") from exc


def _post_merge_dispatches(
    client: GitHubMergeClient,
    identity: dict[str, Any],
    merge_sha: str,
    changed_paths: list[str],
) -> tuple[list[str], list[str]]:
    planned: list[tuple[str, dict[str, str]]] = []
    if any(
        path.startswith("templates/starter-workflows/")
        or path in CROSS_REPO_TRIGGER_PATHS
        for path in changed_paths
    ):
        planned.append(
            (
                CROSS_REPO_DISPATCH_WORKFLOW,
                {
                    "source_commit": merge_sha,
                    "previous_source_commit": identity["base_sha"],
                    "create_pr": "true",
                    "dry_run": "false",
                    "manual_review_on_divergence": "true",
                    "manual_review_delivery": "pr-comment",
                    "include_normalization_patch": "true",
                    "python_version": "3.11",
                },
            )
        )
    if any(path in REF_SYNC_TRIGGER_PATHS for path in changed_paths):
        planned.append(
            (
                REF_SYNC_DISPATCH_WORKFLOW,
                {
                    "before_sha": identity["base_sha"],
                    "after_sha": merge_sha,
                    "auto_commit": "true",
                    "auto_push": "false",
                    "python_version": "3.11",
                },
            )
        )

    dispatched: list[str] = []
    failed: list[str] = []
    for workflow, inputs in planned:
        try:
            client.dispatch_workflow(workflow, ref=ALLOWED_BASE_REF, inputs=inputs)
            dispatched.append(workflow)
        except (AutoMergeError, coordinator.CoordinatorError):
            failed.append(workflow)
    return dispatched, failed


def merge_clean_dev_pr(
    client: GitHubMergeClient,
    receipt: dict[str, Any],
    *,
    expected_head_sha: str,
) -> dict[str, Any]:
    identity = validate_clean_receipt(receipt)
    if expected_head_sha != identity["head_sha"] or not SHA_RE.fullmatch(expected_head_sha):
        raise AutoMergeError("expected_head_mismatch")
    prefix = client.allowed_prefix
    pr = _mapping(client.get(f"{prefix}/pulls/{identity['pr_number']}"))
    head = _mapping(pr.get("head"))
    base = _mapping(pr.get("base"))
    head_repo = _mapping(head.get("repo"))
    if (
        pr.get("state") != "open"
        or pr.get("draft") is True
        or _text(base.get("ref")) != ALLOWED_BASE_REF
        or _text(base.get("ref")) in FORBIDDEN_BASE_REFS
        or _text(base.get("sha")) != identity["base_sha"]
        or _text(head.get("ref")) != identity["head_ref"]
        or _text(head.get("sha")) != identity["head_sha"]
        or cycle_contract._canonical_slug(_text(head_repo.get("full_name")))
        != identity["repository_slug"]
    ):
        raise AutoMergeError("live_pull_request_drift")
    reviews = client.paginated(f"{prefix}/pulls/{identity['pr_number']}/reviews")
    if "CHANGES_REQUESTED" in _latest_human_verdicts(reviews).values():
        raise AutoMergeError("human_changes_requested")
    files = client.paginated(f"{prefix}/pulls/{identity['pr_number']}/files")
    changed_paths = sorted(
        {
            _text(_mapping(value).get("filename"))
            for value in files
            if _text(_mapping(value).get("filename"))
        }
    )
    if not changed_paths or any(not coordinator._valid_path(path) for path in changed_paths):
        raise AutoMergeError("invalid_changed_paths")
    merge = client.merge_exact_head(identity, _text(pr.get("title")) or "Merge pull request")
    merge_sha = _text(merge.get("sha"))
    if merge.get("merged") is not True or not SHA_RE.fullmatch(merge_sha):
        raise AutoMergeError("merge_not_confirmed")
    dispatched, dispatch_failures = _post_merge_dispatches(
        client, identity, merge_sha, changed_paths
    )
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "merged" if not dispatch_failures else "merged_with_downstream_failure",
        "repository_slug": identity["repository_slug"],
        "pr_number": identity["pr_number"],
        "base_ref": identity["base_ref"],
        "head_ref": identity["head_ref"],
        "head_sha": identity["head_sha"],
        "merge_commit_sha": merge_sha,
        "merge_method": "merge",
        "branch_deleted": False,
        "changed_paths_digest": _digest(changed_paths),
        "downstream_dispatches": dispatched,
        "downstream_dispatch_failures": dispatch_failures,
        "coordinator_receipt_digest": _digest(receipt),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--coordinator-receipt", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    try:
        receipt = _load_object(Path(args.coordinator_receipt))
        identity = validate_clean_receipt(receipt)
        if (
            cycle_contract._canonical_slug(args.repository) != identity["repository_slug"]
            or args.pr_number != identity["pr_number"]
        ):
            raise AutoMergeError("invocation_identity_mismatch")
        client = GitHubMergeClient(
            os.environ.get("GITHUB_API_URL", "https://api.github.com"),
            os.environ.get("GITHUB_TOKEN", ""),
            args.repository,
        )
        result = merge_clean_dev_pr(
            client,
            receipt,
            expected_head_sha=args.expected_head_sha,
        )
    except (AutoMergeError, coordinator.CoordinatorError) as exc:
        code = getattr(exc, "code", "invalid_state")
        _write_object(
            Path(args.out),
            {
                "schema": RECEIPT_SCHEMA,
                "status": "blocked",
                "code": code,
                "repository_slug": cycle_contract._canonical_slug(args.repository),
                "pr_number": args.pr_number,
                "expected_head_sha": args.expected_head_sha,
                "branch_deleted": False,
            },
        )
        raise SystemExit(f"dev auto-merge failed: {code}") from exc
    _write_object(Path(args.out), result)
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "merged":
        raise SystemExit("dev auto-merge completed with downstream dispatch failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
