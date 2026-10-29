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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pullfrog_review_contract as review_contract  # noqa: E402

SNAPSHOT_SCHEMA = "pullfrog-review-fallback-snapshot.v1"
RECEIPT_SCHEMA = "pullfrog-review-fallback-receipt.v1"
RESULT_SCHEMA = "pullfrog-review-fallback-result.v1"
RESULT_RECEIPT_SCHEMA = "pullfrog-review-fallback-result-receipt.v1"
REREVIEW_RESULT_SCHEMA = "pullfrog-exact-head-rereview-result.v1"
REREVIEW_RECEIPT_SCHEMA = "pullfrog-exact-head-rereview-receipt.v1"
REREVIEW_RECONCILIATION_SCHEMA = "pullfrog-rereview-thread-reconciliation.v1"
TOKEN_LEASE_SCHEMA = "pullfrog-review-fallback-token-lease.v1"
TOKEN_REVOCATION_SCHEMA = "pullfrog-review-fallback-token-revocation.v1"
PRIMARY_MODEL = "openai/gpt-sol"
PRIMARY_RESOLVED_MODEL = "gpt-6.1-sol"
FALLBACK_MODEL = "openai/gpt-astra"
FALLBACK_RESOLVED_MODEL = "gpt-6-astra"
EFFORT = "xhigh"
PULLFROG_APP = review_contract.PULLFROG_APP
PULLFROG_LOGIN = review_contract.PULLFROG_LOGIN
PRIMARY_CHECK_NAME = review_contract.PULLFROG_CHECK
PRIMARY_WORKFLOW_PATH = ".github/workflows/pullfrog.yml"
FALLBACK_WORKFLOW_PATH = ".github/workflows/pullfrog-review-fallback.yml"
GATE_CHECK_NAME = review_contract.GATE_NAME
GATE_APP = review_contract.GATE_APP
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_OUTCOME_BYTES = 4096
MAX_PAGES = 5
MAX_ITEMS = 500
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_SLUG_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?/[A-Za-z0-9._-]{1,100}$"
)
INSTALLATION_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]{20,512}$")
RUN_ID_RE = re.compile(r"/actions/runs/(?P<run_id>[1-9][0-9]*)(?:/|$)")
REVIEW_MARKER = review_contract.REVIEW_MARKER
PULLFROG_TOKEN_ENDPOINT = "https://pullfrog.com/api/github/installation-token"
PULLFROG_OIDC_AUDIENCE = "pullfrog-api"
REVIEW_TOKEN_PERMISSIONS = {
    "contents": "read",
    "pull_requests": "write",
}

RESOLVE_REVIEW_THREAD_MUTATION = """
mutation ResolvePullfrogReviewThread($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}
"""

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


def _bounded_json_response(
    request: urllib.request.Request,
    error_code: str,
) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise FallbackError(error_code) from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FallbackError(error_code)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FallbackError(error_code) from exc
    if not isinstance(value, dict):
        raise FallbackError(error_code)
    return value


def mint_review_token(
    oidc_request_url: str,
    oidc_request_token: str,
    repository_slug: str,
) -> tuple[str, dict[str, Any]]:
    """Mint one Pullfrog App token limited to review publication authority."""

    if not REPOSITORY_SLUG_RE.fullmatch(repository_slug):
        raise FallbackError("invalid_token_repository")
    if not oidc_request_url or not oidc_request_token:
        raise FallbackError("missing_oidc_credentials")
    try:
        parsed = urllib.parse.urlsplit(oidc_request_url)
    except ValueError as exc:
        raise FallbackError("invalid_oidc_request_url") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise FallbackError("invalid_oidc_request_url")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "audience"]
    query.append(("audience", PULLFROG_OIDC_AUDIENCE))
    audience_url = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )
    oidc_request = urllib.request.Request(
        audience_url,
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {oidc_request_token}",
            "User-Agent": "agent-toolkit-pullfrog-review-fallback",
        },
    )
    oidc_response = _bounded_json_response(oidc_request, "oidc_token_request_failed")
    oidc_token = _text(oidc_response.get("value"))
    if not oidc_token or len(oidc_token) > 16_384 or any(character.isspace() for character in oidc_token):
        raise FallbackError("invalid_oidc_token")

    repository_name = repository_slug.split("/", 1)[1]
    endpoint = PULLFROG_TOKEN_ENDPOINT + "?" + urllib.parse.urlencode({"repos": repository_name})
    payload = json.dumps(
        {"permissions": REVIEW_TOKEN_PERMISSIONS},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    token_request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {oidc_token}",
            "Content-Type": "application/json",
            "User-Agent": "agent-toolkit-pullfrog-review-fallback",
        },
    )
    token_response = _bounded_json_response(token_request, "review_token_request_failed")
    credential = _text(token_response.get("token"))
    expires_at = _text(token_response.get("expires_at"))
    if not INSTALLATION_TOKEN_RE.fullmatch(credential) or not expires_at:
        raise FallbackError("invalid_review_token_response")
    return credential, {
        "schema": TOKEN_LEASE_SCHEMA,
        "status": "active",
        "repository": repository_slug,
        "permissions": REVIEW_TOKEN_PERMISSIONS,
        "expires_at": expires_at,
        "actor": PULLFROG_LOGIN,
        "raw_token_included": False,
    }


def _append_secret_output(path: Path, credential: str, expires_at: str) -> None:
    if not INSTALLATION_TOKEN_RE.fullmatch(credential):
        raise FallbackError("invalid_review_token_output")
    print(f"::add-mask::{credential}")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"credential={credential}\n")
        handle.write(f"expires_at={expires_at}\n")


def revoke_review_token(api_url: str, credential: str, repository_slug: str) -> dict[str, Any]:
    if not api_url.startswith("https://") or not REPOSITORY_SLUG_RE.fullmatch(repository_slug):
        raise FallbackError("invalid_token_revocation_configuration")
    if not INSTALLATION_TOKEN_RE.fullmatch(credential):
        raise FallbackError("invalid_review_token")
    request = urllib.request.Request(
        api_url.rstrip("/") + "/installation/token",
        method="DELETE",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {credential}",
            "User-Agent": "agent-toolkit-pullfrog-review-fallback",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in {200, 204}:
                raise FallbackError("review_token_revocation_failed")
            response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise FallbackError("review_token_revocation_failed") from exc
    return {
        "schema": TOKEN_REVOCATION_SCHEMA,
        "status": "revoked",
        "repository": repository_slug,
        "raw_token_included": False,
    }


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


def _gate_external_id(
    repository_slug: str,
    pr_number: int,
    head_sha: str,
    base_sha: str,
) -> str:
    return review_contract.gate_external_id(
        {
            "repository_slug": repository_slug,
            "pr_number": pr_number,
            "base_ref": "dev",
            "base_sha": base_sha,
            "head_ref": "feat/review",
            "head_sha": head_sha,
            "head_repository_slug": repository_slug,
            "base_repository_slug": repository_slug,
        }
    )


def _valid_complete_review(review: dict[str, Any], head_sha: str) -> bool:
    return review_contract.valid_complete_review(review, head_sha)


def _selected_complete_review(reviews: list[Any], head_sha: str) -> dict[str, Any]:
    return review_contract.select_complete_review(reviews, head_sha)


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
    contract_receipt = review_contract.evaluate_contract(
        {
            "schema": review_contract.SNAPSHOT_SCHEMA,
            "expected_identity": expected,
            "observed_identity": observed,
            "reviews": reviews,
            "review_comments": _list(snapshot.get("review_comments")),
            "review_threads": _list(snapshot.get("review_threads")),
            "check_runs": _list(snapshot.get("check_runs")),
        }
    )
    partial_review_count = _integer(
        _mapping(contract_receipt.get("review")).get("partial_review_count")
    ) or 0
    comments = [
        _mapping(raw)
        for raw in _list(snapshot.get("review_comments"))
        if _text(_mapping(raw).get("commit_id")) == head_sha
        and _text(_mapping(_mapping(raw).get("user")).get("login")) == PULLFROG_LOGIN
    ]

    external_id = _gate_external_id(
        repository_slug, pr_number or 0, head_sha, base_sha
    )
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
        if contract_receipt.get("status") == "clean":
            status = "primary_valid"
        elif contract_receipt.get("status") == "findings":
            blockers.append("primary_verdict_has_findings")
        else:
            blockers.extend(
                _text(item) for item in _list(contract_receipt.get("blockers"))
            )
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
            "review_contract_status": _text(contract_receipt.get("status")),
            "review_contract_digest": _text(contract_receipt.get("evidence_digest")),
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

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        value = self.request("POST", "/graphql", {"query": query, "variables": variables})
        if not isinstance(value, dict) or value.get("errors"):
            raise FallbackError("github_graphql_invalid_response")
        return value

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
    review_threads = review_contract.collect_review_threads(client, expected_identity)
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
        "review_threads": review_threads,
        "check_runs": check_runs,
    }


def verify_live_identity(
    client: GitHubClient,
    pr_number: int,
    expected_head_sha: str,
    expected_base_sha: str,
    run_attempt: int,
) -> dict[str, Any]:
    if run_attempt != 1:
        raise FallbackError("fallback_run_attempt_consumed")
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
    token_lease: dict[str, Any],
    token_revocation: dict[str, Any],
    token_revocation_outcome: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    if coordinator.get("schema") != RECEIPT_SCHEMA or coordinator.get("status") != "fallback_ready":
        raise FallbackError("invalid_fallback_coordinator_receipt")
    if outcome != "success":
        blockers.append("fallback_action_failed")
    expected_token_lease = {
        "schema": TOKEN_LEASE_SCHEMA,
        "status": "active",
        "repository": coordinator.get("repository"),
        "permissions": REVIEW_TOKEN_PERMISSIONS,
        "actor": PULLFROG_LOGIN,
        "raw_token_included": False,
    }
    for key, expected in expected_token_lease.items():
        if token_lease.get(key) != expected:
            blockers.append(f"invalid_review_token_lease_{key}")
    if not _text(token_lease.get("expires_at")):
        blockers.append("invalid_review_token_lease_expiry")
    expected_revocation = {
        "schema": TOKEN_REVOCATION_SCHEMA,
        "status": "revoked",
        "repository": coordinator.get("repository"),
        "raw_token_included": False,
    }
    for key, expected in expected_revocation.items():
        if token_revocation.get(key) != expected:
            blockers.append(f"invalid_review_token_revocation_{key}")
    if token_revocation_outcome != "success":
        blockers.append("review_token_revocation_failed")
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
    contract_receipt: dict[str, Any] = {}
    if review_id:
        review = _mapping(client.get(f"{prefix}/pulls/{coordinator['pr_number']}/reviews/{review_id}"))
        all_comments = client.paginated(f"{prefix}/pulls/{coordinator['pr_number']}/comments")
        comments = [
            _mapping(item)
            for item in all_comments
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
        checks_payload = _mapping(
            client.get(
                f"{prefix}/commits/{coordinator['head_sha']}/check-runs?per_page=100"
            )
        )
        check_runs = _list(checks_payload.get("check_runs"))
        if (_integer(checks_payload.get("total_count")) or len(check_runs)) != len(check_runs):
            blockers.append("fallback_check_collection_truncated")
        review_threads = review_contract.collect_review_threads(client, identity)
        contract_receipt = review_contract.evaluate_contract(
            {
                "schema": review_contract.SNAPSHOT_SCHEMA,
                "expected_identity": identity,
                "observed_identity": identity,
                "reviews": [review],
                "review_comments": all_comments,
                "review_threads": review_threads,
                "check_runs": check_runs,
            }
        )
        expected_contract_status = "clean" if verdict == "clean" else "findings"
        if contract_receipt.get("status") != expected_contract_status:
            blockers.append("fallback_review_contract_mismatch")
        if _integer(_mapping(contract_receipt.get("review")).get("finding_count")) != finding_count:
            blockers.append("fallback_contract_finding_count_mismatch")

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
        "review_contract_status": _text(contract_receipt.get("status")),
        "review_contract_digest": _text(contract_receipt.get("evidence_digest")),
        "blockers": sorted(set(blockers)),
        "result_digest": _digest(result),
        "raw_text_included": False,
    }


def verify_exact_head_rereview_result(
    client: GitHubClient,
    expected_pr_number: int,
    expected_head_sha: str,
    expected_base_sha: str,
    outcome: str,
    result: dict[str, Any],
    token_lease: dict[str, Any],
    token_revocation: dict[str, Any],
    token_revocation_outcome: str,
) -> dict[str, Any]:
    """Validate one Sol re-review and the complete exact-head contract.

    This verifier is deliberately independent from fallback authorization: a
    successful bounded remediation always gets one Sol re-review attempt, while
    Astra remains reserved for the separately gated refusal fallback.
    """

    blockers: list[str] = []
    if (
        expected_pr_number < 1
        or not SHA_RE.fullmatch(expected_head_sha)
        or not SHA_RE.fullmatch(expected_base_sha)
    ):
        raise FallbackError("invalid_expected_rereview_identity")
    if outcome != "success":
        blockers.append("rereview_action_failed")

    expected_token_lease = {
        "schema": TOKEN_LEASE_SCHEMA,
        "status": "active",
        "repository": client.repository_slug,
        "permissions": REVIEW_TOKEN_PERMISSIONS,
        "actor": PULLFROG_LOGIN,
        "raw_token_included": False,
    }
    for key, expected in expected_token_lease.items():
        if token_lease.get(key) != expected:
            blockers.append(f"invalid_rereview_token_lease_{key}")
    if not _text(token_lease.get("expires_at")):
        blockers.append("invalid_rereview_token_lease_expiry")
    expected_revocation = {
        "schema": TOKEN_REVOCATION_SCHEMA,
        "status": "revoked",
        "repository": client.repository_slug,
        "raw_token_included": False,
    }
    for key, expected in expected_revocation.items():
        if token_revocation.get(key) != expected:
            blockers.append(f"invalid_rereview_token_revocation_{key}")
    if token_revocation_outcome != "success":
        blockers.append("rereview_token_revocation_failed")

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
        blockers.append("invalid_rereview_result_shape")
    expected_pairs = {
        "schema": REREVIEW_RESULT_SCHEMA,
        "status": "review_submitted",
        "repository": client.repository_slug,
        "pr_number": expected_pr_number,
        "base_sha": expected_base_sha,
        "head_sha": expected_head_sha,
        "model": PRIMARY_MODEL,
        "effort": EFFORT,
    }
    for key, expected in expected_pairs.items():
        if result.get(key) != expected:
            blockers.append(f"rereview_result_{key}_mismatch")
    review_id = _integer(result.get("review_id"))
    finding_count = _integer(result.get("finding_count"))
    verdict = _text(result.get("verdict"))
    if not review_id or finding_count is None or finding_count < 0:
        blockers.append("invalid_rereview_result_values")
    if verdict == "clean" and finding_count != 0:
        blockers.append("clean_rereview_has_findings")
    elif verdict == "findings" and (finding_count is None or finding_count < 1):
        blockers.append("finding_rereview_has_no_findings")
    elif verdict not in {"clean", "findings"}:
        blockers.append("invalid_rereview_verdict")

    prefix = f"/repos/{client.repository_slug}"
    pr = _mapping(client.get(f"{prefix}/pulls/{expected_pr_number}"))
    identity = _identity(client.repository_slug, pr)
    expected_identity = {
        "repository_slug": client.repository_slug,
        "pr_number": expected_pr_number,
        "base_sha": expected_base_sha,
        "head_sha": expected_head_sha,
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            blockers.append(f"live_{key}_drift")
    if identity.get("state") != "open":
        blockers.append("pull_request_not_open")
    if identity.get("head_repository_slug") != client.repository_slug:
        blockers.append("fork_head_forbidden")
    if identity.get("base_repository_slug") != client.repository_slug:
        blockers.append("base_repository_mismatch")

    comments: list[Any] = []
    contract_receipt: dict[str, Any] = {}
    if review_id:
        review = _mapping(
            client.get(
                f"{prefix}/pulls/{expected_pr_number}/reviews/{review_id}"
            )
        )
        reviews = client.paginated(f"{prefix}/pulls/{expected_pr_number}/reviews")
        all_comments = client.paginated(
            f"{prefix}/pulls/{expected_pr_number}/comments"
        )
        comments = [
            _mapping(item)
            for item in all_comments
            if _integer(_mapping(item).get("pull_request_review_id")) == review_id
        ]
        if not _valid_complete_review(review, expected_head_sha):
            blockers.append("invalid_exact_head_rereview")
        body = _text(review.get("body"))
        if f"Using `{PRIMARY_RESOLVED_MODEL}`" not in body:
            blockers.append("rereview_model_unverified")
        if verdict == "clean" and "No new issues found" not in body:
            blockers.append("clean_rereview_verdict_unverified")
        if len(comments) != finding_count:
            blockers.append("rereview_finding_count_mismatch")
        if any(
            _text(item.get("commit_id")) != expected_head_sha
            or _text(_mapping(item.get("user")).get("login")) != PULLFROG_LOGIN
            for item in comments
        ):
            blockers.append("invalid_exact_head_rereview_comment")
        checks_payload = _mapping(
            client.get(
                f"{prefix}/commits/{expected_head_sha}/check-runs?per_page=100"
            )
        )
        check_runs = _list(checks_payload.get("check_runs"))
        if (_integer(checks_payload.get("total_count")) or len(check_runs)) != len(
            check_runs
        ):
            blockers.append("rereview_check_collection_truncated")
        review_threads = review_contract.collect_review_threads(client, identity)
        contract_receipt = review_contract.evaluate_contract(
            {
                "schema": review_contract.SNAPSHOT_SCHEMA,
                "expected_identity": identity,
                "observed_identity": identity,
                "reviews": reviews,
                "review_comments": all_comments,
                "review_threads": review_threads,
                "check_runs": check_runs,
            }
        )
        expected_contract_statuses = (
            {"clean", "reconciliation_required"}
            if verdict == "clean"
            else {"findings"}
        )
        if contract_receipt.get("status") not in expected_contract_statuses:
            blockers.append("rereview_contract_mismatch")
        if (
            contract_receipt.get("status") == "reconciliation_required"
            and contract_receipt.get("blockers")
            != ["unresolved_pullfrog_review_threads"]
        ):
            blockers.append("invalid_rereview_reconciliation_state")
        if _integer(_mapping(contract_receipt.get("review")).get("review_id")) != review_id:
            blockers.append("rereview_not_authoritative_complete_review")
        if (
            _integer(_mapping(contract_receipt.get("review")).get("finding_count"))
            != finding_count
        ):
            blockers.append("rereview_contract_finding_count_mismatch")

    return {
        "schema": REREVIEW_RECEIPT_SCHEMA,
        "status": "valid" if not blockers else "invalid",
        "repository": client.repository_slug,
        "pr_number": expected_pr_number,
        "base_sha": expected_base_sha,
        "head_sha": expected_head_sha,
        "model": PRIMARY_MODEL,
        "resolved_model": PRIMARY_RESOLVED_MODEL,
        "effort": EFFORT,
        "review_id": review_id or 0,
        "verdict": verdict,
        "finding_count": finding_count if finding_count is not None else -1,
        "review_comment_count": len(comments),
        "review_contract_status": _text(contract_receipt.get("status")),
        "review_contract_digest": _text(contract_receipt.get("evidence_digest")),
        "blockers": sorted(set(blockers)),
        "result_digest": _digest(result),
        "raw_text_included": False,
    }


def reconcile_rereview_threads(
    client: GitHubClient,
    rereview_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Resolve only stale Pullfrog-owned threads after a valid clean re-review.

    The caller has no provider credential. All candidates are re-read and
    validated before the first mutation, then the complete exact-head contract
    is re-evaluated after the bounded mutations.
    """

    blockers: list[str] = []
    if rereview_receipt.get("schema") != REREVIEW_RECEIPT_SCHEMA:
        raise FallbackError("invalid_rereview_reconciliation_receipt")
    if (
        rereview_receipt.get("status") != "valid"
        or rereview_receipt.get("verdict") != "clean"
        or _integer(rereview_receipt.get("finding_count")) != 0
        or rereview_receipt.get("blockers") != []
    ):
        raise FallbackError("rereview_not_clean_for_reconciliation")

    pr_number = _integer(rereview_receipt.get("pr_number")) or 0
    base_sha = _text(rereview_receipt.get("base_sha"))
    head_sha = _text(rereview_receipt.get("head_sha"))
    review_id = _integer(rereview_receipt.get("review_id")) or 0
    if (
        rereview_receipt.get("repository") != client.repository_slug
        or pr_number < 1
        or review_id < 1
        or not SHA_RE.fullmatch(base_sha)
        or not SHA_RE.fullmatch(head_sha)
    ):
        raise FallbackError("invalid_rereview_reconciliation_identity")

    prefix = f"/repos/{client.repository_slug}"
    pr = _mapping(client.get(f"{prefix}/pulls/{pr_number}"))
    identity = _identity(client.repository_slug, pr)
    expected_identity = {
        "repository_slug": client.repository_slug,
        "pr_number": pr_number,
        "base_sha": base_sha,
        "head_sha": head_sha,
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            blockers.append(f"live_{key}_drift")
    if identity.get("state") != "open":
        blockers.append("pull_request_not_open")
    if identity.get("head_repository_slug") != client.repository_slug:
        blockers.append("fork_head_forbidden")
    if identity.get("base_repository_slug") != client.repository_slug:
        blockers.append("base_repository_mismatch")

    reviews = client.paginated(f"{prefix}/pulls/{pr_number}/reviews")
    comments = client.paginated(f"{prefix}/pulls/{pr_number}/comments")
    checks_payload = _mapping(
        client.get(f"{prefix}/commits/{head_sha}/check-runs?per_page=100")
    )
    check_runs = _list(checks_payload.get("check_runs"))
    if (_integer(checks_payload.get("total_count")) or len(check_runs)) != len(
        check_runs
    ):
        blockers.append("rereview_check_collection_truncated")
    threads_before = review_contract.collect_review_threads(client, identity)
    contract_before = review_contract.evaluate_contract(
        {
            "schema": review_contract.SNAPSHOT_SCHEMA,
            "expected_identity": identity,
            "observed_identity": identity,
            "reviews": reviews,
            "review_comments": comments,
            "review_threads": threads_before,
            "check_runs": check_runs,
        }
    )
    before_status = _text(contract_before.get("status"))
    before_review = _mapping(contract_before.get("review"))
    if _integer(before_review.get("review_id")) != review_id:
        blockers.append("rereview_authority_drift")
    if _integer(before_review.get("finding_count")) != 0:
        blockers.append("rereview_findings_present")
    if before_status not in {"clean", "reconciliation_required"}:
        blockers.append("rereview_contract_not_reconcilable")
    if (
        before_status == "reconciliation_required"
        and contract_before.get("blockers")
        != ["unresolved_pullfrog_review_threads"]
    ):
        blockers.append("invalid_rereview_reconciliation_state")
    if (
        before_status == "reconciliation_required"
        and _text(rereview_receipt.get("review_contract_digest"))
        != _text(contract_before.get("evidence_digest"))
    ):
        blockers.append("rereview_contract_digest_drift")

    unresolved = review_contract.unresolved_pullfrog_threads(threads_before)
    if len(unresolved) > 100:
        blockers.append("rereview_thread_reconciliation_limit")
    node_ids = [_text(item.get("node_id")) for item in unresolved]
    if len(set(node_ids)) != len(node_ids):
        blockers.append("duplicate_rereview_thread_id")
    for item in unresolved:
        if not review_contract.THREAD_NODE_ID_RE.fullmatch(_text(item.get("node_id"))):
            blockers.append("invalid_rereview_thread_id")
        if (_integer(item.get("review_id")) or 0) < 1:
            blockers.append("invalid_rereview_thread_review")
        if not review_contract.valid_path(_text(item.get("path"))):
            blockers.append("invalid_rereview_thread_path")
        if (_integer(item.get("line")) or 0) < 1:
            blockers.append("invalid_rereview_thread_line")
        if _integer(item.get("review_id")) == review_id:
            blockers.append("current_rereview_thread_not_reconcilable")

    resolved_count = 0
    if not blockers:
        for node_id in node_ids:
            payload = client.graphql(
                RESOLVE_REVIEW_THREAD_MUTATION,
                {"threadId": node_id},
            )
            thread = _mapping(
                _mapping(_mapping(payload.get("data")).get("resolveReviewThread")).get(
                    "thread"
                )
            )
            if thread.get("id") != node_id or thread.get("isResolved") is not True:
                blockers.append("rereview_thread_resolution_unconfirmed")
                break
            resolved_count += 1

    contract_after: dict[str, Any] = {}
    if not blockers:
        pr_after = _mapping(client.get(f"{prefix}/pulls/{pr_number}"))
        identity_after = _identity(client.repository_slug, pr_after)
        for key, expected in expected_identity.items():
            if identity_after.get(key) != expected:
                blockers.append(f"post_reconciliation_{key}_drift")
        reviews_after = client.paginated(f"{prefix}/pulls/{pr_number}/reviews")
        comments_after = client.paginated(f"{prefix}/pulls/{pr_number}/comments")
        checks_after_payload = _mapping(
            client.get(f"{prefix}/commits/{head_sha}/check-runs?per_page=100")
        )
        checks_after = _list(checks_after_payload.get("check_runs"))
        if (
            _integer(checks_after_payload.get("total_count")) or len(checks_after)
        ) != len(checks_after):
            blockers.append("post_reconciliation_check_collection_truncated")
        threads_after = review_contract.collect_review_threads(client, identity_after)
        contract_after = review_contract.evaluate_contract(
            {
                "schema": review_contract.SNAPSHOT_SCHEMA,
                "expected_identity": identity_after,
                "observed_identity": identity_after,
                "reviews": reviews_after,
                "review_comments": comments_after,
                "review_threads": threads_after,
                "check_runs": checks_after,
            }
        )
        if (
            contract_after.get("status") != "clean"
            or contract_after.get("blockers") != []
            or _integer(_mapping(contract_after.get("review")).get("review_id"))
            != review_id
            or _integer(
                _mapping(contract_after.get("threads")).get(
                    "unresolved_pullfrog_count"
                )
            )
            != 0
        ):
            blockers.append("post_reconciliation_contract_not_clean")

    return {
        "schema": REREVIEW_RECONCILIATION_SCHEMA,
        "status": "clean" if not blockers else "invalid",
        "repository": client.repository_slug,
        "pr_number": pr_number,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "review_id": review_id,
        "resolved_thread_count": resolved_count,
        "before_contract_status": before_status,
        "before_contract_digest": _text(contract_before.get("evidence_digest")),
        "after_contract_status": _text(contract_after.get("status")),
        "after_contract_digest": _text(contract_after.get("evidence_digest")),
        "blockers": sorted(set(blockers)),
        "raw_text_included": False,
    }


def _publish_gate_check(
    client: GitHubClient,
    *,
    head_sha: str,
    external_id: str,
    details_url: str,
    title: str,
    summary: str,
    check_status: str,
    conclusion: str,
) -> dict[str, Any]:
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
    checks_payload = _mapping(
        client.get(f"{prefix}/commits/{head_sha}/check-runs?per_page=100")
    )
    existing = _selected_gate(
        _list(checks_payload.get("check_runs")), external_id, head_sha
    )
    if existing:
        check_id = _integer(existing.get("id"))
        update_payload = dict(payload)
        update_payload.pop("head_sha", None)
        response = _mapping(
            client.patch(f"{prefix}/check-runs/{check_id}", update_payload)
        )
        operation = "updated"
    else:
        response = _mapping(client.post(f"{prefix}/check-runs", payload))
        operation = "created"
    check_id = _integer(response.get("id"))
    if not check_id:
        raise FallbackError("gate_check_publish_failed")
    return {
        "schema": review_contract.GATE_SCHEMA,
        "operation": operation,
        "check_run_id": check_id,
        "status": check_status,
        "conclusion": conclusion,
        "head_sha": head_sha,
        "external_id": external_id,
    }


def publish_rereview_gate(
    client: GitHubClient,
    receipt: dict[str, Any],
    details_url: str,
) -> dict[str, Any]:
    if receipt.get("schema") != REREVIEW_RECONCILIATION_SCHEMA:
        raise FallbackError("invalid_rereview_gate_reconciliation_receipt")
    required = {
        "schema",
        "status",
        "repository",
        "pr_number",
        "base_sha",
        "head_sha",
        "review_id",
        "resolved_thread_count",
        "before_contract_status",
        "before_contract_digest",
        "after_contract_status",
        "after_contract_digest",
        "blockers",
        "raw_text_included",
    }
    if set(receipt) != required or receipt.get("raw_text_included") is not False:
        raise FallbackError("invalid_rereview_gate_reconciliation_shape")
    identity = {
        "repository_slug": receipt.get("repository"),
        "pr_number": receipt.get("pr_number"),
        "base_sha": receipt.get("base_sha"),
        "head_sha": receipt.get("head_sha"),
    }
    if (
        identity["repository_slug"] != client.repository_slug
        or not _integer(identity["pr_number"])
        or not SHA_RE.fullmatch(_text(identity["base_sha"]))
        or not SHA_RE.fullmatch(_text(identity["head_sha"]))
    ):
        raise FallbackError("invalid_rereview_gate_identity")
    resolved_count = _integer(receipt.get("resolved_thread_count"))
    before_status = _text(receipt.get("before_contract_status"))
    before_digest = _text(receipt.get("before_contract_digest"))
    after_digest = _text(receipt.get("after_contract_digest"))
    clean = (
        receipt.get("status") == "clean"
        and receipt.get("after_contract_status") == "clean"
        and receipt.get("blockers") == []
        and (_integer(receipt.get("review_id")) or 0) > 0
        and resolved_count is not None
        and resolved_count >= 0
        and before_status in {"clean", "reconciliation_required"}
        and bool(re.fullmatch(r"[0-9a-f]{64}", before_digest))
        and bool(re.fullmatch(r"[0-9a-f]{64}", after_digest))
        and not (before_status == "clean" and resolved_count != 0)
        and not (before_status == "reconciliation_required" and resolved_count < 1)
    )
    return _publish_gate_check(
        client,
        head_sha=_text(identity["head_sha"]),
        external_id=review_contract.gate_external_id(identity),
        details_url=details_url,
        title=(
            "Pullfrog exact-head re-review produced a clean valid verdict"
            if clean
            else "Pullfrog exact-head re-review failed closed"
        ),
        summary=(
            "The bounded Sol re-review and complete exact-head evidence were validated."
            if clean
            else "The bounded Sol re-review did not produce complete clean exact-head evidence."
        ),
        check_status="completed",
        conclusion="success" if clean else "failure",
    )


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
        if (
            result_receipt.get("status") == "valid"
            and result_receipt.get("review_contract_status") == "clean"
            and _integer(result_receipt.get("finding_count")) == 0
        ):
            title = "Pullfrog Astra fallback produced a clean valid verdict"
            summary = "One clean structured exact-head Astra fallback verdict was validated."
            conclusion = "success"
        elif result_receipt.get("status") == "valid":
            title = "Pullfrog Astra fallback produced findings"
            summary = "The exact-head fallback verdict is complete but contains findings."
            conclusion = "failure"
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
    return _publish_gate_check(
        client,
        head_sha=head_sha,
        external_id=external_id,
        details_url=details_url,
        title=title,
        summary=summary,
        check_status=check_status,
        conclusion=conclusion,
    )


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
    identity.add_argument("--run-attempt", required=True, type=int)
    identity.add_argument("--out", required=True)

    mint = sub.add_parser("mint-review-token")
    mint.add_argument("--repository", required=True)
    mint.add_argument("--github-output", required=True)
    mint.add_argument("--out", required=True)

    revoke = sub.add_parser("revoke-review-token")
    revoke.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    revoke.add_argument("--repository", required=True)
    revoke.add_argument("--token-env", default="PULLFROG_REVIEW_TOKEN")
    revoke.add_argument("--out", required=True)

    verify = sub.add_parser("verify-fallback-result")
    verify.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    verify.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    verify.add_argument("--repository", required=True)
    verify.add_argument("--coordinator", required=True)
    verify.add_argument("--action-outcome-file", required=True)
    verify.add_argument("--action-result-file", required=True)
    verify.add_argument("--token-lease-file", required=True)
    verify.add_argument("--token-revocation-file", required=True)
    verify.add_argument("--token-revocation-outcome-file", required=True)
    verify.add_argument("--out", required=True)

    verify_rereview = sub.add_parser("verify-rereview-result")
    verify_rereview.add_argument(
        "--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com")
    )
    verify_rereview.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    verify_rereview.add_argument("--repository", required=True)
    verify_rereview.add_argument("--pr-number", required=True, type=int)
    verify_rereview.add_argument("--expected-head-sha", required=True)
    verify_rereview.add_argument("--expected-base-sha", required=True)
    verify_rereview.add_argument("--action-outcome-file", required=True)
    verify_rereview.add_argument("--action-result-file", required=True)
    verify_rereview.add_argument("--token-lease-file", required=True)
    verify_rereview.add_argument("--token-revocation-file", required=True)
    verify_rereview.add_argument("--token-revocation-outcome-file", required=True)
    verify_rereview.add_argument("--out", required=True)

    reconcile_rereview = sub.add_parser("reconcile-rereview-threads")
    reconcile_rereview.add_argument(
        "--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com")
    )
    reconcile_rereview.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    reconcile_rereview.add_argument("--repository", required=True)
    reconcile_rereview.add_argument("--receipt", required=True)
    reconcile_rereview.add_argument("--out", required=True)

    publish = sub.add_parser("publish-gate")
    publish.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    publish.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    publish.add_argument("--repository", required=True)
    publish.add_argument("--coordinator", required=True)
    publish.add_argument("--details-url", required=True)
    publish.add_argument("--enabled", choices=("true", "false"), required=True)
    publish.add_argument("--result-receipt")
    publish.add_argument("--out", required=True)

    publish_rereview = sub.add_parser("publish-rereview-gate")
    publish_rereview.add_argument(
        "--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com")
    )
    publish_rereview.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    publish_rereview.add_argument("--repository", required=True)
    publish_rereview.add_argument("--receipt", required=True)
    publish_rereview.add_argument("--details-url", required=True)
    publish_rereview.add_argument("--out", required=True)

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
                    args.run_attempt,
                ),
            }
            _write_object(Path(args.out), identity_receipt)
            return 0
        if args.command == "mint-review-token":
            credential, token_receipt = mint_review_token(
                os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", ""),
                os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", ""),
                args.repository,
            )
            _write_object(Path(args.out), token_receipt)
            _append_secret_output(
                Path(args.github_output),
                credential,
                _text(token_receipt.get("expires_at")),
            )
            return 0
        if args.command == "revoke-review-token":
            credential = os.environ.get(args.token_env, "")
            receipt = revoke_review_token(args.api_url, credential, args.repository)
            _write_object(Path(args.out), receipt)
            return 0
        if args.command == "verify-fallback-result":
            coordinator = _load_object(Path(args.coordinator))
            outcome = _load_outcome(Path(args.action_outcome_file))
            result = _load_object(Path(args.action_result_file))
            token_lease = _load_object(Path(args.token_lease_file))
            token_revocation = _load_object(Path(args.token_revocation_file))
            token_revocation_outcome = _load_outcome(Path(args.token_revocation_outcome_file))
            client = GitHubClient(args.api_url, args.token, args.repository)
            receipt = verify_fallback_result(
                client,
                coordinator,
                outcome,
                result,
                token_lease,
                token_revocation,
                token_revocation_outcome,
            )
            _write_object(Path(args.out), receipt)
            return 0 if receipt["status"] == "valid" else 2
        if args.command == "verify-rereview-result":
            outcome = _load_outcome(Path(args.action_outcome_file))
            result = _load_object(Path(args.action_result_file))
            token_lease = _load_object(Path(args.token_lease_file))
            token_revocation = _load_object(Path(args.token_revocation_file))
            token_revocation_outcome = _load_outcome(
                Path(args.token_revocation_outcome_file)
            )
            client = GitHubClient(args.api_url, args.token, args.repository)
            receipt = verify_exact_head_rereview_result(
                client,
                args.pr_number,
                args.expected_head_sha,
                args.expected_base_sha,
                outcome,
                result,
                token_lease,
                token_revocation,
                token_revocation_outcome,
            )
            _write_object(Path(args.out), receipt)
            return 0 if receipt["status"] == "valid" else 2
        if args.command == "reconcile-rereview-threads":
            rereview_receipt = _load_object(Path(args.receipt))
            client = GitHubClient(args.api_url, args.token, args.repository)
            reconciliation = reconcile_rereview_threads(client, rereview_receipt)
            _write_object(Path(args.out), reconciliation)
            return 0 if reconciliation["status"] == "clean" else 2
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
        if args.command == "publish-rereview-gate":
            receipt = _load_object(Path(args.receipt))
            client = GitHubClient(args.api_url, args.token, args.repository)
            publication = publish_rereview_gate(client, receipt, args.details_url)
            _write_object(Path(args.out), publication)
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
        elif args.command == "verify-rereview-result":
            failure = {
                "schema": REREVIEW_RECEIPT_SCHEMA,
                "status": "invalid",
                "repository": args.repository,
                "pr_number": args.pr_number,
                "base_sha": args.expected_base_sha,
                "head_sha": args.expected_head_sha,
                "model": PRIMARY_MODEL,
                "resolved_model": PRIMARY_RESOLVED_MODEL,
                "effort": EFFORT,
                "review_id": 0,
                "verdict": "",
                "finding_count": -1,
                "review_comment_count": 0,
                "review_contract_status": "",
                "review_contract_digest": "",
                "blockers": [exc.code],
                "result_digest": "",
                "raw_text_included": False,
            }
            _write_object(Path(args.out), failure)
        elif args.command == "reconcile-rereview-threads":
            try:
                source_receipt = _load_object(Path(args.receipt))
            except FallbackError:
                source_receipt = {}
            failure = {
                "schema": REREVIEW_RECONCILIATION_SCHEMA,
                "status": "invalid",
                "repository": args.repository,
                "pr_number": _integer(source_receipt.get("pr_number")) or 0,
                "base_sha": _text(source_receipt.get("base_sha")),
                "head_sha": _text(source_receipt.get("head_sha")),
                "review_id": _integer(source_receipt.get("review_id")) or 0,
                "resolved_thread_count": 0,
                "before_contract_status": "",
                "before_contract_digest": "",
                "after_contract_status": "",
                "after_contract_digest": "",
                "blockers": [exc.code],
                "raw_text_included": False,
            }
            _write_object(Path(args.out), failure)
        print(exc.code, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
