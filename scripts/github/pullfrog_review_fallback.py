#!/usr/bin/env python3
"""Bounded Pullfrog review-model fallback controller.

The controller recognizes one exact OpenAI cybersecurity-policy refusal from a
trusted Pullfrog primary review run, proves that no complete exact-head verdict
exists, and authorizes at most one Astra fallback for the unchanged PR head and
base. Raw provider and review text never reaches its sanitized receipts.
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
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA = "pullfrog-review-fallback-snapshot.v1"
RECEIPT_SCHEMA = "pullfrog-review-fallback-receipt.v1"
RESULT_SCHEMA = "pullfrog-review-fallback-result.v1"
RESULT_RECEIPT_SCHEMA = "pullfrog-review-fallback-result-receipt.v1"
PRIMARY_MODEL = "openai/gpt-sol"
PRIMARY_RESOLVED_MODEL = "gpt-6.1-sol"
FALLBACK_MODEL = "openai/gpt-astra"
FALLBACK_RESOLVED_MODEL = "gpt-6-astra"
EFFORT = "xhigh"
PULLFROG_APP = "pullfrog"
PULLFROG_LOGIN = "pullfrog[bot]"
PRIMARY_CHECK_NAME = "pullfrog"
PRIMARY_WORKFLOW_PATH = ".github/workflows/pullfrog.yml"
FALLBACK_WORKFLOW_PATH = ".github/workflows/pullfrog-review-fallback.yml"
GATE_CHECK_NAME = "pullfrog-review-gate"
GATE_APP = "github-actions"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_OUTCOME_BYTES = 4096
MAX_PAGES = 5
MAX_ITEMS = 500
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"/actions/runs/(?P<run_id>[1-9][0-9]*)(?:/|$)")
REVIEW_MARKER = "PULLFROG_DIVIDER_DO_NOT_REMOVE_PLZ"

# Keep this narrow. Any wording change is a fail-closed policy update, not a
# fuzzy retry. The two entries differ only in the apostrophe GitHub may render.
CYBER_REFUSAL_MESSAGES = {
    "action failed: provider error: This content was flagged for possible cybersecurity risk. If this seems wrong, try rephrasing your request. If you’re doing authorized security work that requires more cyber permissive safeguards, apply for Daybreak access via https://platform.openai.com/settings/organization/status-and-access before retrying.",
    "action failed: provider error: This content was flagged for possible cybersecurity risk. If this seems wrong, try rephrasing your request. If you're doing authorized security work that requires more cyber permissive safeguards, apply for Daybreak access via https://platform.openai.com/settings/organization/status-and-access before retrying.",
}


class FallbackError(Exception):
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


def _load_bytes(path: Path, max_bytes: int, error_code: str) -> bytes:
    try:
        if path.stat().st_size > max_bytes:
            raise FallbackError(error_code)
        raw = path.read_bytes()
    except OSError as exc:
        raise FallbackError(error_code) from exc
    if len(raw) > max_bytes:
        raise FallbackError(error_code)
    return raw


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            _load_bytes(path, MAX_RESPONSE_BYTES, "invalid_json_file").decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FallbackError("invalid_json_file") from exc
    if not isinstance(value, dict):
        raise FallbackError("invalid_json_root")
    return value


def _load_outcome(path: Path) -> str:
    try:
        return _load_bytes(path, MAX_OUTCOME_BYTES, "invalid_outcome_file").decode(
            "utf-8"
        ).strip()
    except UnicodeDecodeError as exc:
        raise FallbackError("invalid_outcome_file") from exc


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _identity(repository_slug: str, pr: dict[str, Any]) -> dict[str, Any]:
    head = _mapping(pr.get("head"))
    base = _mapping(pr.get("base"))
    head_repo = _mapping(head.get("repo"))
    base_repo = _mapping(base.get("repo"))
    return {
        "repository_slug": repository_slug,
        "pr_number": _integer(pr.get("number")),
        "state": _text(pr.get("state")),
        "base_ref": _text(base.get("ref")),
        "base_sha": _text(base.get("sha")),
        "base_repository_slug": _text(base_repo.get("full_name")),
        "head_ref": _text(head.get("ref")),
        "head_sha": _text(head.get("sha")),
        "head_repository_slug": _text(head_repo.get("full_name")),
    }


def _event_pr(check_run: dict[str, Any]) -> dict[str, Any]:
    prs = [_mapping(item) for item in _list(check_run.get("pull_requests"))]
    if len(prs) != 1:
        raise FallbackError("primary_check_pr_cardinality")
    return prs[0]


def _gate_external_id(repository_slug: str, pr_number: int, head_sha: str) -> str:
    return f"pullfrog-review-gate:v1:{repository_slug}:{pr_number}:{head_sha}"


def _valid_complete_review(review: dict[str, Any], head_sha: str) -> bool:
    return bool(
        _integer(review.get("id"))
        and _text(review.get("commit_id")) == head_sha
        and _text(_mapping(review.get("user")).get("login")) == PULLFROG_LOGIN
        and _text(review.get("submitted_at"))
        and REVIEW_MARKER in _text(review.get("body"))
    )


def _selected_complete_review(reviews: list[Any], head_sha: str) -> dict[str, Any]:
    eligible = [
        _mapping(item)
        for item in reviews
        if _valid_complete_review(_mapping(item), head_sha)
    ]
    if not eligible:
        return {}
    return max(eligible, key=lambda item: (_text(item.get("submitted_at")), _integer(item.get("id")) or 0))


def _selected_gate(check_runs: list[Any], external_id: str, head_sha: str) -> dict[str, Any]:
    eligible: list[dict[str, Any]] = []
    for raw in check_runs:
        item = _mapping(raw)
        if (
            _text(item.get("name")) == GATE_CHECK_NAME
            and _text(_mapping(item.get("app")).get("slug")) == GATE_APP
            and _text(item.get("head_sha")) == head_sha
            and _text(item.get("external_id")) == external_id
            and (_integer(item.get("id")) or 0) > 0
        ):
            eligible.append(item)
    return max(eligible, key=lambda item: _integer(item.get("id")) or 0) if eligible else {}


def _refusal_evidence(jobs: list[Any], annotations: list[Any]) -> tuple[bool, dict[str, Any], list[str]]:
    blockers: list[str] = []
    pullfrog_jobs = [item for item in (_mapping(raw) for raw in jobs) if _text(item.get("name")) == "pullfrog"]
    if len(pullfrog_jobs) != 1:
        return False, {}, ["primary_job_cardinality"]
    job = pullfrog_jobs[0]
    if _text(job.get("status")) != "completed" or _text(job.get("conclusion")) != "failure":
        blockers.append("primary_job_not_failed")
    steps = [_mapping(item) for item in _list(job.get("steps"))]
    action_steps = [item for item in steps if _text(item.get("name")) == "Run review-only agent"]
    if len(action_steps) != 1 or _text(action_steps[0].get("conclusion")) != "failure":
        blockers.append("primary_action_step_not_failed")
    failed_steps = [item for item in steps if _text(item.get("conclusion")) == "failure"]
    if len(failed_steps) != 1 or not action_steps or failed_steps[0] is not action_steps[0]:
        blockers.append("additional_primary_failed_step")
    job_id = _integer(job.get("id"))
    job_annotations = [
        _mapping(raw)
        for raw in annotations
        if _integer(_mapping(raw).get("job_id")) == job_id
    ]
    failures = [item for item in job_annotations if _text(item.get("annotation_level")) == "failure"]
    matched = [
        item
        for item in failures
        if _text(item.get("message")) in CYBER_REFUSAL_MESSAGES
    ]
    if len(matched) != 1:
        blockers.append("cyber_refusal_signature_mismatch")
    if len(failures) != 1:
        blockers.append("additional_primary_failure_annotation")
    evidence = {
        "job_id": job_id,
        "job_conclusion": _text(job.get("conclusion")),
        "failure_annotation_count": len(failures),
        "matched_refusal_count": len(matched),
        "refusal_digest": _digest(_text(matched[0].get("message"))) if matched else "",
    }
    return not blockers, evidence, blockers


def evaluate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise FallbackError("invalid_snapshot_schema")

    repository_slug = _text(snapshot.get("repository_slug"))
    repository = _mapping(snapshot.get("repository"))
    check_run = _mapping(snapshot.get("primary_check"))
    workflow_run = _mapping(snapshot.get("primary_workflow_run"))
    expected = _mapping(snapshot.get("expected_identity"))
    observed = _identity(repository_slug, _mapping(snapshot.get("observed_pull_request")))
    head_sha = _text(observed.get("head_sha"))
    base_sha = _text(observed.get("base_sha"))
    pr_number = _integer(observed.get("pr_number"))

    if not repository_slug or _text(repository.get("full_name")) != repository_slug:
        blockers.append("repository_identity_mismatch")
    if not pr_number or not SHA_RE.fullmatch(head_sha) or not SHA_RE.fullmatch(base_sha):
        blockers.append("invalid_live_pr_identity")
    if expected != observed:
        blockers.append("pull_request_identity_drift")
    if _text(observed.get("state")) != "open":
        blockers.append("pull_request_not_open")
    if _text(observed.get("head_repository_slug")) != repository_slug:
        blockers.append("fork_head_forbidden")
    if _text(observed.get("base_repository_slug")) != repository_slug:
        blockers.append("base_repository_mismatch")

    if _text(check_run.get("name")) != PRIMARY_CHECK_NAME:
        blockers.append("wrong_primary_check_name")
    if _text(_mapping(check_run.get("app")).get("slug")) != PULLFROG_APP:
        blockers.append("wrong_primary_check_app")
    if _text(check_run.get("head_sha")) != head_sha:
        blockers.append("primary_check_head_mismatch")
    if _text(check_run.get("status")) != "completed":
        blockers.append("primary_check_not_completed")
    source_workflow_path = _text(workflow_run.get("path"))
    fallback_source_run = source_workflow_path == FALLBACK_WORKFLOW_PATH
    if not fallback_source_run:
        if source_workflow_path != PRIMARY_WORKFLOW_PATH:
            blockers.append("wrong_primary_workflow_path")
        if _text(workflow_run.get("event")) != "workflow_dispatch":
            blockers.append("wrong_primary_workflow_event")
        if _text(_mapping(workflow_run.get("actor")).get("login")) != PULLFROG_LOGIN:
            blockers.append("wrong_primary_workflow_actor")

    reviews = _list(snapshot.get("reviews"))
    complete_review = _selected_complete_review(reviews, head_sha)
    partial_review_count = sum(
        1
        for raw in reviews
        if _text(_mapping(raw).get("commit_id")) == head_sha
        and _text(_mapping(_mapping(raw).get("user")).get("login")) == PULLFROG_LOGIN
        and not _valid_complete_review(_mapping(raw), head_sha)
    )
    comments = [
        _mapping(raw)
        for raw in _list(snapshot.get("review_comments"))
        if _text(_mapping(raw).get("commit_id")) == head_sha
        and _text(_mapping(_mapping(raw).get("user")).get("login")) == PULLFROG_LOGIN
    ]

    external_id = _gate_external_id(repository_slug, pr_number or 0, head_sha)
    prior_gate = _selected_gate(_list(snapshot.get("check_runs")), external_id, head_sha)
    conclusion = _text(check_run.get("conclusion"))
    refusal_ok, refusal, refusal_blockers = _refusal_evidence(
        _list(snapshot.get("primary_jobs")), _list(snapshot.get("primary_annotations"))
    )

    status = "stopped"
    authorized = False
    if fallback_source_run:
        # A Pullfrog check emitted by this workflow is evidence for this run's
        # finalizer, never a new primary failure and never a recursive retry.
        status = "ignored_fallback_run"
        blockers = []
    elif blockers:
        pass
    elif conclusion == "success":
        if complete_review:
            status = "primary_valid"
        else:
            blockers.append("missing_complete_primary_verdict")
    elif conclusion == "failure":
        blockers.extend(refusal_blockers)
        if complete_review:
            blockers.append("complete_primary_verdict_already_exists")
        if prior_gate:
            blockers.append("fallback_already_attempted_for_head")
        if not blockers and refusal_ok:
            status = "fallback_ready"
            authorized = True
    else:
        blockers.append("primary_check_not_success_or_failure")

    review_id = _integer(complete_review.get("id")) or 0
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "authorized_fallback": authorized,
        "repository": repository_slug,
        "pr_number": pr_number,
        "base_ref": _text(observed.get("base_ref")),
        "base_sha": base_sha,
        "head_ref": _text(observed.get("head_ref")),
        "head_sha": head_sha,
        "primary": {
            "model": PRIMARY_MODEL,
            "resolved_model": PRIMARY_RESOLVED_MODEL,
            "effort": EFFORT,
            "check_run_id": _integer(check_run.get("id")),
            "check_conclusion": conclusion,
            "workflow_run_id": _integer(workflow_run.get("id")),
            "complete_review_id": review_id,
            "partial_review_count": partial_review_count,
            "exact_head_comment_count": len(comments),
            "refusal": refusal,
        },
        "fallback": {
            "model": FALLBACK_MODEL,
            "resolved_model": FALLBACK_RESOLVED_MODEL,
            "effort": EFFORT,
            "attempt_limit_per_head": 1,
            "prior_gate_check_run_id": _integer(prior_gate.get("id")),
        },
        "gate": {
            "name": GATE_CHECK_NAME,
            "external_id": external_id,
            "initial_conclusion": (
                "success" if status == "primary_valid" else "in_progress" if status == "fallback_ready" else "failure"
            ),
        },
        "blockers": sorted(set(blockers)),
        "evidence_digest": _digest(
            {
                "expected": expected,
                "observed": observed,
                "check_run_id": _integer(check_run.get("id")),
                "workflow_run_id": _integer(workflow_run.get("id")),
                "review_id": review_id,
                "comment_ids": sorted(_integer(item.get("id")) or 0 for item in comments),
                "refusal": refusal,
            }
        ),
        "raw_text_included": False,
    }
    return receipt


class GitHubClient:
    def __init__(self, api_url: str, token: str, repository_slug: str):
        if not api_url.startswith("https://") or not token or not repository_slug:
            raise FallbackError("invalid_github_client_configuration")
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.repository_slug = repository_slug

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self.api_url + path
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "agent-toolkit-pullfrog-review-fallback",
                "X-GitHub-Api-Version": "2022-11-28",
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise FallbackError("github_api_request_failed") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise FallbackError("github_api_response_too_large")
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FallbackError("github_api_invalid_json") from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("PATCH", path, payload)

    def paginated(self, path: str) -> list[Any]:
        result: list[Any] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, MAX_PAGES + 1):
            payload = self.get(f"{path}{separator}per_page=100&page={page}")
            items = _list(payload)
            result.extend(items)
            if len(result) > MAX_ITEMS:
                raise FallbackError("github_api_item_limit")
            if len(items) < 100:
                return result
        raise FallbackError("github_api_page_limit")


def collect_snapshot(
    client: GitHubClient,
    check_run_id: int,
    expected_pr_number: int | None = None,
    expected_head_sha: str = "",
    expected_base_sha: str = "",
) -> dict[str, Any]:
    prefix = f"/repos/{client.repository_slug}"
    repository = _mapping(client.get(prefix))
    check_run = _mapping(client.get(f"{prefix}/check-runs/{check_run_id}"))
    event_pr = _event_pr(check_run)
    pr_number = _integer(event_pr.get("number"))
    if not pr_number:
        raise FallbackError("invalid_primary_check_pr")
    observed_pr = _mapping(client.get(f"{prefix}/pulls/{pr_number}"))
    expected_identity = _identity(client.repository_slug, observed_pr)

    event_head = _mapping(event_pr.get("head"))
    event_base = _mapping(event_pr.get("base"))
    if _text(event_head.get("sha")) != expected_identity["head_sha"]:
        raise FallbackError("event_head_drift")
    if _text(event_base.get("sha")) != expected_identity["base_sha"]:
        raise FallbackError("event_base_drift")
    if expected_pr_number is not None and pr_number != expected_pr_number:
        raise FallbackError("dispatch_pr_mismatch")
    if expected_head_sha and expected_identity["head_sha"] != expected_head_sha:
        raise FallbackError("dispatch_head_mismatch")
    if expected_base_sha and expected_identity["base_sha"] != expected_base_sha:
        raise FallbackError("dispatch_base_mismatch")

    run_match = RUN_ID_RE.search(_text(check_run.get("details_url")))
    if not run_match:
        raise FallbackError("missing_primary_workflow_run_id")
    run_id = int(run_match.group("run_id"))
    workflow_run = _mapping(client.get(f"{prefix}/actions/runs/{run_id}"))
    jobs_payload = _mapping(client.get(f"{prefix}/actions/runs/{run_id}/jobs?per_page=100"))
    jobs = _list(jobs_payload.get("jobs"))
    if (_integer(jobs_payload.get("total_count")) or len(jobs)) != len(jobs):
        raise FallbackError("primary_job_collection_truncated")
    annotations: list[dict[str, Any]] = []
    for job in jobs:
        job_id = _integer(_mapping(job).get("id"))
        if not job_id:
            raise FallbackError("invalid_primary_job_id")
        for annotation in client.paginated(f"{prefix}/check-runs/{job_id}/annotations"):
            item = dict(_mapping(annotation))
            item["job_id"] = job_id
            annotations.append(item)

    reviews = client.paginated(f"{prefix}/pulls/{pr_number}/reviews")
    comments = client.paginated(f"{prefix}/pulls/{pr_number}/comments")
    check_payload = _mapping(client.get(f"{prefix}/commits/{expected_identity['head_sha']}/check-runs?per_page=100"))
    check_runs = _list(check_payload.get("check_runs"))
    if (_integer(check_payload.get("total_count")) or len(check_runs)) != len(check_runs):
        raise FallbackError("check_run_collection_truncated")
    observed_after = _mapping(client.get(f"{prefix}/pulls/{pr_number}"))
    if _identity(client.repository_slug, observed_after) != expected_identity:
        raise FallbackError("pull_request_changed_during_collection")

    return {
        "schema": SNAPSHOT_SCHEMA,
        "repository_slug": client.repository_slug,
        "repository": repository,
        "expected_identity": expected_identity,
        "observed_pull_request": observed_after,
        "primary_check": check_run,
        "primary_workflow_run": workflow_run,
        "primary_jobs": jobs,
        "primary_annotations": annotations,
        "reviews": reviews,
        "review_comments": comments,
        "check_runs": check_runs,
    }


def verify_live_identity(
    client: GitHubClient,
    pr_number: int,
    expected_head_sha: str,
    expected_base_sha: str,
) -> dict[str, Any]:
    if pr_number < 1 or not SHA_RE.fullmatch(expected_head_sha) or not SHA_RE.fullmatch(expected_base_sha):
        raise FallbackError("invalid_expected_identity")
    pr = _mapping(client.get(f"/repos/{client.repository_slug}/pulls/{pr_number}"))
    identity = _identity(client.repository_slug, pr)
    if identity.get("state") != "open":
        raise FallbackError("pull_request_not_open")
    if identity.get("head_repository_slug") != client.repository_slug:
        raise FallbackError("fork_head_forbidden")
    if identity.get("base_repository_slug") != client.repository_slug:
        raise FallbackError("base_repository_mismatch")
    if identity.get("head_sha") != expected_head_sha:
        raise FallbackError("live_head_sha_drift")
    if identity.get("base_sha") != expected_base_sha:
        raise FallbackError("live_base_sha_drift")
    return identity


def _append_outputs(path: Path, receipt: dict[str, Any]) -> None:
    values = {
        "status": receipt.get("status"),
        "authorized_fallback": str(bool(receipt.get("authorized_fallback"))).lower(),
        "repository": receipt.get("repository"),
        "pr_number": receipt.get("pr_number"),
        "head_sha": receipt.get("head_sha"),
        "base_sha": receipt.get("base_sha"),
        "gate_external_id": _mapping(receipt.get("gate")).get("external_id"),
    }
    with path.open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def verify_fallback_result(
    client: GitHubClient,
    coordinator: dict[str, Any],
    outcome: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if coordinator.get("schema") != RECEIPT_SCHEMA or coordinator.get("status") != "fallback_ready":
        raise FallbackError("invalid_fallback_coordinator_receipt")
    if outcome != "success":
        blockers.append("fallback_action_failed")
    required = {
        "schema",
        "status",
        "repository",
        "pr_number",
        "base_sha",
        "head_sha",
        "model",
        "effort",
        "review_id",
        "verdict",
        "finding_count",
    }
    if set(result) != required:
        blockers.append("invalid_fallback_result_shape")
    expected_pairs = {
        "schema": RESULT_SCHEMA,
        "status": "review_submitted",
        "repository": coordinator.get("repository"),
        "pr_number": coordinator.get("pr_number"),
        "base_sha": coordinator.get("base_sha"),
        "head_sha": coordinator.get("head_sha"),
        "model": FALLBACK_MODEL,
        "effort": EFFORT,
    }
    for key, expected in expected_pairs.items():
        if result.get(key) != expected:
            blockers.append(f"fallback_result_{key}_mismatch")
    review_id = _integer(result.get("review_id"))
    finding_count = _integer(result.get("finding_count"))
    verdict = _text(result.get("verdict"))
    if not review_id or finding_count is None or finding_count < 0:
        blockers.append("invalid_fallback_result_values")
    if verdict == "clean" and finding_count != 0:
        blockers.append("clean_fallback_has_findings")
    elif verdict == "findings" and (finding_count is None or finding_count < 1):
        blockers.append("finding_fallback_has_no_findings")
    elif verdict not in {"clean", "findings"}:
        blockers.append("invalid_fallback_verdict")

    prefix = f"/repos/{client.repository_slug}"
    pr = _mapping(client.get(f"{prefix}/pulls/{coordinator['pr_number']}"))
    identity = _identity(client.repository_slug, pr)
    for key in ("repository_slug", "pr_number", "base_sha", "head_sha"):
        expected = coordinator.get("repository") if key == "repository_slug" else coordinator.get(key)
        if identity.get(key) != expected:
            blockers.append(f"live_{key}_drift")

    review: dict[str, Any] = {}
    comments: list[Any] = []
    if review_id:
        review = _mapping(client.get(f"{prefix}/pulls/{coordinator['pr_number']}/reviews/{review_id}"))
        comments = [
            _mapping(item)
            for item in client.paginated(f"{prefix}/pulls/{coordinator['pr_number']}/comments")
            if _integer(_mapping(item).get("pull_request_review_id")) == review_id
        ]
        if not _valid_complete_review(review, _text(coordinator.get("head_sha"))):
            blockers.append("invalid_exact_head_fallback_review")
        body = _text(review.get("body"))
        if f"Using `{FALLBACK_RESOLVED_MODEL}`" not in body:
            blockers.append("fallback_review_model_unverified")
        if verdict == "clean" and "No new issues found" not in body:
            blockers.append("clean_fallback_verdict_unverified")
        if len(comments) != finding_count:
            blockers.append("fallback_finding_count_mismatch")
        if any(
            _text(item.get("commit_id")) != coordinator.get("head_sha")
            or _text(_mapping(item.get("user")).get("login")) != PULLFROG_LOGIN
            for item in comments
        ):
            blockers.append("invalid_exact_head_fallback_comment")

    return {
        "schema": RESULT_RECEIPT_SCHEMA,
        "status": "valid" if not blockers else "invalid",
        "repository": coordinator.get("repository"),
        "pr_number": coordinator.get("pr_number"),
        "base_sha": coordinator.get("base_sha"),
        "head_sha": coordinator.get("head_sha"),
        "model": FALLBACK_MODEL,
        "resolved_model": FALLBACK_RESOLVED_MODEL,
        "effort": EFFORT,
        "review_id": review_id or 0,
        "verdict": verdict,
        "finding_count": finding_count if finding_count is not None else -1,
        "review_comment_count": len(comments),
        "blockers": sorted(set(blockers)),
        "result_digest": _digest(result),
        "raw_text_included": False,
    }


def publish_gate(
    client: GitHubClient,
    coordinator: dict[str, Any],
    details_url: str,
    enabled: bool,
    result_receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    if coordinator.get("schema") != RECEIPT_SCHEMA:
        raise FallbackError("invalid_gate_coordinator_receipt")
    status = _text(coordinator.get("status"))
    title = "Pullfrog review gate failed closed"
    summary = "The exact-head Pullfrog review evidence did not authorize a valid review verdict."
    check_status = "completed"
    conclusion = "failure"
    if result_receipt is not None:
        if result_receipt.get("schema") != RESULT_RECEIPT_SCHEMA:
            raise FallbackError("invalid_gate_result_receipt")
        if result_receipt.get("status") == "valid":
            title = "Pullfrog Astra fallback produced a valid verdict"
            summary = "One structured exact-head Astra fallback verdict was validated."
            conclusion = "success"
        else:
            title = "Pullfrog Astra fallback failed closed"
            summary = "The single authorized fallback did not produce a valid structured exact-head verdict."
    elif status == "primary_valid":
        title = "Pullfrog primary review produced a valid verdict"
        summary = "The exact-head Sol review completed with a valid Pullfrog verdict."
        conclusion = "success"
    elif status == "fallback_ready" and enabled:
        title = "Pullfrog Astra fallback in progress"
        summary = "One exact-head Astra fallback was authorized after the recognized Sol policy refusal."
        check_status = "in_progress"
        conclusion = ""
    elif status == "fallback_ready":
        title = "Pullfrog fallback activation required"
        summary = "A fallback is eligible, but the repository fallback activation flag is disabled."
        conclusion = "action_required"

    external_id = _text(_mapping(coordinator.get("gate")).get("external_id"))
    head_sha = _text(coordinator.get("head_sha"))
    prefix = f"/repos/{client.repository_slug}"
    payload: dict[str, Any] = {
        "name": GATE_CHECK_NAME,
        "head_sha": head_sha,
        "external_id": external_id,
        "details_url": details_url,
        "status": check_status,
        "output": {"title": title, "summary": summary},
    }
    if check_status == "completed":
        payload["conclusion"] = conclusion
    checks_payload = _mapping(client.get(f"{prefix}/commits/{head_sha}/check-runs?per_page=100"))
    existing = _selected_gate(_list(checks_payload.get("check_runs")), external_id, head_sha)
    if existing:
        check_id = _integer(existing.get("id"))
        update_payload = dict(payload)
        update_payload.pop("head_sha", None)
        response = _mapping(client.patch(f"{prefix}/check-runs/{check_id}", update_payload))
        operation = "updated"
    else:
        response = _mapping(client.post(f"{prefix}/check-runs", payload))
        operation = "created"
    check_id = _integer(response.get("id"))
    if not check_id:
        raise FallbackError("gate_check_publish_failed")
    return {
        "schema": "pullfrog-review-gate-publication.v1",
        "operation": operation,
        "check_run_id": check_id,
        "status": check_status,
        "conclusion": conclusion,
        "head_sha": head_sha,
        "external_id": external_id,
    }


def _summary(path: Path, value: dict[str, Any]) -> None:
    lines = [
        "## Pullfrog review model fallback",
        "",
        f"- Status: `{value.get('status', 'unknown')}`",
        f"- PR: `#{value.get('pr_number', 0)}`",
        f"- Head: `{value.get('head_sha', '')}`",
        f"- Primary: `{PRIMARY_MODEL}` at `{EFFORT}`",
        f"- Fallback: `{FALLBACK_MODEL}` at `{EFFORT}`",
    ]
    blockers = _list(value.get("blockers"))
    if blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    evaluate = sub.add_parser("evaluate-github")
    evaluate.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    evaluate.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    evaluate.add_argument("--repository", required=True)
    evaluate.add_argument("--primary-check-run-id", required=True, type=int)
    evaluate.add_argument("--expected-pr-number", type=int)
    evaluate.add_argument("--expected-head-sha", default="")
    evaluate.add_argument("--expected-base-sha", default="")
    evaluate.add_argument("--out", required=True)
    evaluate.add_argument("--github-output")

    fixture = sub.add_parser("evaluate-snapshot")
    fixture.add_argument("--snapshot", required=True)
    fixture.add_argument("--out", required=True)

    identity = sub.add_parser("verify-identity")
    identity.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    identity.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    identity.add_argument("--repository", required=True)
    identity.add_argument("--pr-number", required=True, type=int)
    identity.add_argument("--expected-head-sha", required=True)
    identity.add_argument("--expected-base-sha", required=True)
    identity.add_argument("--out", required=True)

    verify = sub.add_parser("verify-fallback-result")
    verify.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    verify.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    verify.add_argument("--repository", required=True)
    verify.add_argument("--coordinator", required=True)
    verify.add_argument("--action-outcome-file", required=True)
    verify.add_argument("--action-result-file", required=True)
    verify.add_argument("--out", required=True)

    publish = sub.add_parser("publish-gate")
    publish.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    publish.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    publish.add_argument("--repository", required=True)
    publish.add_argument("--coordinator", required=True)
    publish.add_argument("--details-url", required=True)
    publish.add_argument("--enabled", choices=("true", "false"), required=True)
    publish.add_argument("--result-receipt")
    publish.add_argument("--out", required=True)

    summarize = sub.add_parser("summarize")
    summarize.add_argument("--receipt", required=True)
    summarize.add_argument("--github-step-summary", required=True)

    args = parser.parse_args()
    try:
        if args.command == "evaluate-snapshot":
            receipt = evaluate_snapshot(_load_object(Path(args.snapshot)))
            _write_object(Path(args.out), receipt)
            return 0
        if args.command == "evaluate-github":
            client = GitHubClient(args.api_url, args.token, args.repository)
            snapshot = collect_snapshot(
                client,
                args.primary_check_run_id,
                args.expected_pr_number,
                args.expected_head_sha,
                args.expected_base_sha,
            )
            receipt = evaluate_snapshot(snapshot)
            _write_object(Path(args.out), receipt)
            if args.github_output:
                _append_outputs(Path(args.github_output), receipt)
            return 0
        if args.command == "verify-identity":
            client = GitHubClient(args.api_url, args.token, args.repository)
            identity_receipt = {
                "schema": "pullfrog-review-fallback-identity.v1",
                "status": "valid",
                **verify_live_identity(
                    client,
                    args.pr_number,
                    args.expected_head_sha,
                    args.expected_base_sha,
                ),
            }
            _write_object(Path(args.out), identity_receipt)
            return 0
        if args.command == "verify-fallback-result":
            coordinator = _load_object(Path(args.coordinator))
            outcome = _load_outcome(Path(args.action_outcome_file))
            result = _load_object(Path(args.action_result_file))
            client = GitHubClient(args.api_url, args.token, args.repository)
            receipt = verify_fallback_result(client, coordinator, outcome, result)
            _write_object(Path(args.out), receipt)
            return 0 if receipt["status"] == "valid" else 2
        if args.command == "publish-gate":
            coordinator = _load_object(Path(args.coordinator))
            result_receipt = _load_object(Path(args.result_receipt)) if args.result_receipt else None
            client = GitHubClient(args.api_url, args.token, args.repository)
            receipt = publish_gate(
                client,
                coordinator,
                args.details_url,
                args.enabled == "true",
                result_receipt,
            )
            _write_object(Path(args.out), receipt)
            return 0
        if args.command == "summarize":
            _summary(Path(args.github_step_summary), _load_object(Path(args.receipt)))
            return 0
    except FallbackError as exc:
        if args.command == "verify-fallback-result":
            try:
                coordinator = _load_object(Path(args.coordinator))
            except FallbackError:
                coordinator = {}
            failure = {
                "schema": RESULT_RECEIPT_SCHEMA,
                "status": "invalid",
                "repository": coordinator.get("repository", ""),
                "pr_number": coordinator.get("pr_number", 0),
                "base_sha": coordinator.get("base_sha", ""),
                "head_sha": coordinator.get("head_sha", ""),
                "model": FALLBACK_MODEL,
                "resolved_model": FALLBACK_RESOLVED_MODEL,
                "effort": EFFORT,
                "review_id": 0,
                "verdict": "",
                "finding_count": -1,
                "review_comment_count": 0,
                "blockers": [exc.code],
                "result_digest": "",
                "raw_text_included": False,
            }
            _write_object(Path(args.out), failure)
        print(exc.code, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
