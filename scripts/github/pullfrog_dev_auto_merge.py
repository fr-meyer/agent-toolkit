#!/usr/bin/env python3
"""Fail-closed exact-head auto-merge for clean feature PRs targeting dev only.

The irreversible boundary is a normal fast-forward Git push of a locally built
two-parent merge commit. That binds the mutation to both the authorized ``dev``
ref and its exact reviewed tip; GitHub's pull-request merge endpoint cannot
express either base predicate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
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
import pullfrog_destination_guard as destination_guard  # noqa: E402

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
        or not cycle_contract._valid_branch(base_ref)
        or not cycle_contract._valid_branch(head_ref)
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


def _validated_receipt_check_rules(
    receipt: dict[str, Any], identity: dict[str, Any]
) -> dict[str, list[tuple[str, str]]]:
    details = _mapping(receipt.get("checks"))
    if set(details) != {"pullfrog", "pullfrog_approval", "ci", "speculoos"}:
        raise AutoMergeError("invalid_receipt_check_details")
    rules: dict[str, list[tuple[str, str]]] = {}
    for group in ("pullfrog", "pullfrog_approval", "ci", "speculoos"):
        values = _list(details.get(group))
        parsed: list[tuple[str, str]] = []
        if not values:
            raise AutoMergeError("invalid_receipt_check_details")
        for raw in values:
            item = _mapping(raw)
            rule = coordinator._check_rule(item)
            if (
                rule is None
                or item.get("status") != "success"
                or item.get("head_sha") != identity["head_sha"]
                or (_integer(item.get("check_run_id")) or 0) < 1
            ):
                raise AutoMergeError("invalid_receipt_check_details")
            parsed.append(rule)
        if len(set(parsed)) != len(parsed):
            raise AutoMergeError("invalid_receipt_check_details")
        rules[group] = parsed
    if rules["pullfrog"] != [(coordinator.PULLFROG_CHECK, coordinator.PULLFROG_APP)]:
        raise AutoMergeError("invalid_receipt_check_details")
    if rules["pullfrog_approval"] != [
        (coordinator.PULLFROG_APPROVAL_CHECK, coordinator.PULLFROG_APP)
    ]:
        raise AutoMergeError("invalid_receipt_check_details")
    return rules


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
    collection = _mapping(receipt.get("collection"))
    if (
        (_integer(collection.get("changed_paths_count")) or 0) < 1
        or not re.fullmatch(r"[0-9a-f]{64}", _text(collection.get("changed_paths_digest")))
    ):
        raise AutoMergeError("invalid_collection_summary")
    _validated_receipt_check_rules(receipt, identity)
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


def _assert_live_pull_request(pr: dict[str, Any], identity: dict[str, Any]) -> None:
    head = _mapping(pr.get("head"))
    base = _mapping(pr.get("base"))
    head_repo = _mapping(head.get("repo"))
    if (
        pr.get("state") != "open"
        or pr.get("draft") is True
        or _text(base.get("ref")) != identity["base_ref"]
        or _text(base.get("ref")) in FORBIDDEN_BASE_REFS
        or _text(base.get("sha")) != identity["base_sha"]
        or _text(head.get("ref")) != identity["head_ref"]
        or _text(head.get("sha")) != identity["head_sha"]
        or cycle_contract._canonical_slug(_text(head_repo.get("full_name")))
        != identity["repository_slug"]
    ):
        raise AutoMergeError("live_pull_request_drift")


def _refresh_exact_head_evidence(
    client: "GitHubMergeClient",
    receipt: dict[str, Any],
    identity: dict[str, Any],
    *,
    repository: dict[str, Any],
    reviews: list[Any],
    comments: list[Any],
    changed_paths: list[str],
) -> dict[str, Any]:
    rules = _validated_receipt_check_rules(receipt, identity)
    prefix = client.allowed_prefix
    payload = _mapping(
        client.get(f"{prefix}/commits/{identity['head_sha']}/check-runs?per_page=100")
    )
    check_runs = _list(payload.get("check_runs"))
    if _integer(payload.get("total_count")) not in {None, len(check_runs)}:
        raise AutoMergeError("fresh_check_collection_truncated")

    selected: dict[str, list[dict[str, Any]]] = {}
    for group, group_rules in rules.items():
        selected[group] = [
            coordinator._select_check(check_runs, identity["head_sha"], name, app_slug)
            for name, app_slug in group_rules
        ]
        if any(item.get("status") != "success" for item in selected[group]):
            raise AutoMergeError("fresh_required_evidence_not_successful")
        if any(item.get("spoofed_count") or item.get("stale_count") for item in selected[group]):
            raise AutoMergeError("fresh_required_evidence_ambiguous")

    pullfrog = selected["pullfrog"][0]
    approval = selected["pullfrog_approval"][0]
    if (
        pullfrog.get("check_suite_id") is None
        or pullfrog.get("check_suite_id") != approval.get("check_suite_id")
    ):
        raise AutoMergeError("fresh_pullfrog_suite_mismatch")

    review = coordinator._select_review(reviews, identity["head_sha"])
    findings, _, review_comment_count, blockers = coordinator._review_findings(
        review, comments, _text(approval.get("status")), identity["head_sha"]
    )
    if not review or findings or review_comment_count != 0 or blockers:
        raise AutoMergeError("fresh_pullfrog_review_not_clean")

    collection = _mapping(receipt.get("collection"))
    if (
        len(changed_paths) != _integer(collection.get("changed_paths_count"))
        or _digest(changed_paths) != collection.get("changed_paths_digest")
    ):
        raise AutoMergeError("fresh_changed_paths_drift")

    default_branch = _text(repository.get("default_branch"))
    if not cycle_contract._valid_branch(default_branch):
        raise AutoMergeError("invalid_default_branch")
    protected_refs = sorted(
        set((identity["base_ref"], default_branch, *FORBIDDEN_BASE_REFS))
    )
    guard_identity = {
        "slug": identity["repository_slug"],
        "head_repository_slug": identity["head_repository_slug"],
        "pr_number": identity["pr_number"],
        "base_ref": identity["base_ref"],
        "base_sha": identity["base_sha"],
        "head_ref": identity["head_ref"],
        "head_sha": identity["head_sha"],
        "default_branch": default_branch,
        "protected_refs": protected_refs,
    }
    prior_guard = _mapping(receipt.get("destination_guard"))
    attempt = _integer(
        _mapping(prior_guard.get("destination")).get("attempt")
    ) or 1
    fresh_guard = destination_guard.evaluate_guard(
        {
            "schema": destination_guard.INPUT_SCHEMA,
            "expected": guard_identity,
            "observed": guard_identity,
            "request": {
                "destination_repository_slug": identity["repository_slug"],
                "destination_ref": identity["head_ref"],
                "destination_sha": identity["head_sha"],
                "attempt": attempt,
                "changed_paths": changed_paths,
            },
            "first_attempt": {
                "destination_repository_slug": identity["repository_slug"],
                "destination_ref": identity["head_ref"],
                "destination_sha": identity["head_sha"],
            },
        }
    )
    if fresh_guard.get("status") != "allowed" or fresh_guard.get("blockers") != []:
        raise AutoMergeError("fresh_destination_not_allowed")

    return {
        "review_id": _integer(review.get("id")),
        "check_run_ids": {
            group: [item.get("check_run_id") for item in values]
            for group, values in selected.items()
        },
        "destination_guard_digest": _digest(fresh_guard),
    }


class GitHubMergeClient(coordinator.GitHubReadClient):
    """Bounded reader plus one destination-bound, exact-base Git mutation."""

    @staticmethod
    def _git(
        workspace: Path,
        *args: str,
        env: dict[str, str] | None = None,
        code: str = "git_merge_failed",
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=workspace,
                env=env,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AutoMergeError(code) from exc
        if result.returncode != 0:
            raise AutoMergeError(code)
        return result

    def _repository_remote(self) -> str:
        return f"https://github.com/{self.repository_slug}.git"

    def push_exact_merge(self, identity: dict[str, Any], title: str) -> dict[str, Any]:
        """Build and normally push one merge commit onto the reviewed base.

        The generated commit's first parent is the reviewed base SHA. A normal
        (never forced) push to the literal reviewed base ref is therefore a
        server-side compare-and-swap: retargeting cannot redirect it, and a base
        advance makes the push non-fast-forward and fails closed.
        """

        token = self.token
        if not token:
            raise AutoMergeError("missing_github_token")
        remote = self._repository_remote()
        with tempfile.TemporaryDirectory(prefix="pullfrog-auto-merge-") as temporary:
            workspace = Path(temporary)
            askpass = workspace / "git-askpass.sh"
            askpass.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  *Username*) printf '%s\\n' x-access-token ;;\n"
                "  *) printf '%s\\n' \"$GITHUB_TOKEN\" ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            askpass.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            env = os.environ.copy()
            env.update(
                {
                    "GITHUB_TOKEN": token,
                    "GIT_ASKPASS": str(askpass),
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_AUTHOR_NAME": "github-actions[bot]",
                    "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
                    "GIT_COMMITTER_NAME": "github-actions[bot]",
                    "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
                }
            )
            self._git(workspace, "init", "--quiet", env=env)
            self._git(workspace, "remote", "add", "origin", remote, env=env)
            self._git(
                workspace,
                "fetch",
                "--quiet",
                "--no-tags",
                "origin",
                f"refs/heads/{identity['base_ref']}:refs/remotes/origin/base",
                f"refs/pull/{identity['pr_number']}/head:refs/remotes/origin/pull-head",
                env=env,
                code="git_fetch_failed",
            )
            base = self._git(
                workspace, "rev-parse", "refs/remotes/origin/base", env=env
            ).stdout.strip()
            head = self._git(
                workspace, "rev-parse", "refs/remotes/origin/pull-head", env=env
            ).stdout.strip()
            if base != identity["base_sha"] or head != identity["head_sha"]:
                raise AutoMergeError("git_fetch_identity_drift")
            tree = self._git(
                workspace,
                "merge-tree",
                "--write-tree",
                identity["base_sha"],
                identity["head_sha"],
                env=env,
                code="merge_conflict_or_tree_failure",
            ).stdout.strip()
            if not SHA_RE.fullmatch(tree):
                raise AutoMergeError("invalid_merge_tree")
            message = f"{title} (#{identity['pr_number']})"
            merge_sha = self._git(
                workspace,
                "commit-tree",
                tree,
                "-p",
                identity["base_sha"],
                "-p",
                identity["head_sha"],
                "-m",
                message,
                env=env,
                code="merge_commit_creation_failed",
            ).stdout.strip()
            if not SHA_RE.fullmatch(merge_sha):
                raise AutoMergeError("invalid_merge_commit")
            self._git(
                workspace,
                "push",
                "--porcelain",
                "origin",
                f"{merge_sha}:refs/heads/{identity['base_ref']}",
                env=env,
                code="base_compare_and_swap_failed",
            )
        return {
            "merged": True,
            "sha": merge_sha,
            "base_ref": identity["base_ref"],
            "base_sha": identity["base_sha"],
            "head_sha": identity["head_sha"],
            "transport": "normal-fast-forward-push",
        }

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
            client.dispatch_workflow(workflow, ref=identity["base_ref"], inputs=inputs)
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
    _assert_live_pull_request(pr, identity)
    repository = _mapping(client.get(prefix))
    reviews = client.paginated(f"{prefix}/pulls/{identity['pr_number']}/reviews")
    if "CHANGES_REQUESTED" in _latest_human_verdicts(reviews).values():
        raise AutoMergeError("human_changes_requested")
    comments = client.paginated(f"{prefix}/pulls/{identity['pr_number']}/comments")
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
    fresh_evidence = _refresh_exact_head_evidence(
        client,
        receipt,
        identity,
        repository=repository,
        reviews=reviews,
        comments=comments,
        changed_paths=changed_paths,
    )
    _assert_live_pull_request(
        _mapping(client.get(f"{prefix}/pulls/{identity['pr_number']}")), identity
    )
    merge = client.push_exact_merge(identity, _text(pr.get("title")) or "Merge pull request")
    merge_sha = _text(merge.get("sha"))
    if (
        merge.get("merged") is not True
        or not SHA_RE.fullmatch(merge_sha)
        or merge.get("base_ref") != identity["base_ref"]
        or merge.get("base_sha") != identity["base_sha"]
        or merge.get("head_sha") != identity["head_sha"]
        or merge.get("transport") != "normal-fast-forward-push"
    ):
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
        "merge_transport": "normal-fast-forward-push",
        "branch_deleted": False,
        "changed_paths_digest": _digest(changed_paths),
        "fresh_evidence_digest": _digest(fresh_evidence),
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
