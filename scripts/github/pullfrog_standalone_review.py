"""Provider-free exact-head adapter. Input must come from a trusted collector.

trusted_pullfrog_identity is collector configuration, never PR/event-authored data.
No default numeric identity is invented: an unconfigured installation fails closed.
Collection completeness attestations must be set only after all pages are collected.
"""
from __future__ import annotations

import copy
import pullfrog_review_contract as review
from pullfrog_standalone_contract import ContractError, binding, digest, validate_binding, validate_request

SCHEMA = "pullfrog-standalone-review.v1"


def _positive(value):
    return type(value) is int and value > 0


def normalize(request, snapshot, *, current_head_sha=None):
    """Normalize a review-contract snapshot plus binding and trusted collector metadata.

    Additional fields: trusted_pullfrog_identity {app_id, account_id, login, type,
    app_slug}; collection_complete {reviews, review_comments, review_threads,
    check_runs}. Native check evidence is mandatory. Returns no action authority.
    Invalid request/binding raises ContractError; invalid observations are incomplete.
    """
    validate_request(request)
    if type(snapshot) is not dict:
        raise ContractError("invalid_review_snapshot")
    expected_binding = binding(request, head_sha=current_head_sha)
    validate_binding(snapshot.get("binding"), request, head_sha=current_head_sha)
    source = copy.deepcopy(snapshot)
    blockers = []
    configured = source.get("trusted_pullfrog_identity")
    configured = configured if type(configured) is dict else {}
    if not (_positive(configured.get("app_id"))
            and _positive(configured.get("account_id"))
            and configured.get("login") == review.PULLFROG_LOGIN
            and configured.get("type") == "Bot"
            and configured.get("app_slug") == review.PULLFROG_APP):
        blockers.append("unconfigured_pullfrog_immutable_identity")
    complete = source.get("collection_complete", {})
    for field in ("reviews", "review_comments", "review_threads", "check_runs"):
        if type(complete) is not dict or complete.get(field) is not True:
            blockers.append("incomplete_collection_" + field)
        if type(source.get(field)) is not list or len(source[field]) > review.MAX_ITEMS:
            blockers.append("invalid_collection_" + field)
            source[field] = []
        elif any(type(item) is not dict for item in source[field]):
            blockers.append("invalid_collection_" + field)
            source[field] = []
    for key in ("expected_identity", "observed_identity"):
        identity = review.normalize_identity(source.get(key))
        for field in ("repository_slug", "pr_number", "base_ref", "base_sha", "head_ref"):
            if identity.get(field) != request[field]:
                blockers.append("request_review_identity_mismatch")
        if identity["head_sha"] != expected_binding["head_sha"]:
            blockers.append("request_review_head_mismatch")

    def account_ok(value):
        return (type(value) is dict and _positive(value.get("id"))
                and value.get("id") == configured.get("account_id")
                and value.get("login") == review.PULLFROG_LOGIN
                and value.get("type") == "Bot")

    for field in ("reviews", "review_comments"):
        for item in source[field]:
            user = item.get("user", {})
            if type(user) is dict and str(user.get("login", "")).casefold() == review.PULLFROG_LOGIN:
                if not account_ok(user):
                    blockers.append("pullfrog_account_identity_mismatch")
    for item in source["reviews"]:
        if review.valid_complete_review(item, expected_binding["head_sha"]):
            if item.get("state") not in ("COMMENTED", "APPROVED", "CHANGES_REQUESTED"):
                blockers.append("invalid_completed_review_state")
    for item in source["check_runs"]:
        if item.get("name") in (review.PULLFROG_CHECK, review.PULLFROG_APPROVAL_CHECK):
            app = item.get("app", {})
            if (type(app) is not dict or not _positive(app.get("id"))
                    or app.get("id") != configured.get("app_id")
                    or app.get("slug") != review.PULLFROG_APP):
                blockers.append("pullfrog_app_identity_mismatch")
    # The legacy GraphQL collector only returns login. Standalone needs databaseId
    # (or REST id), type and login on thread roots as well, including resolved roots.
    for thread in source["review_threads"]:
        root = review._thread_root(thread)
        author = root.get("author") or root.get("user") or {}
        if type(author) is not dict or not author.get("login"):
            blockers.append("invalid_thread_root_identity")
        elif str(author["login"]).casefold() == review.PULLFROG_LOGIN:
            normalized_author = dict(author)
            normalized_author.setdefault("id", author.get("databaseId"))
            if not account_ok(normalized_author):
                blockers.append("pullfrog_thread_identity_mismatch")
        if type(thread.get("isResolved")) is not bool:
            blockers.append("invalid_thread_resolution")
    contract = review.evaluate_contract(source)
    blockers = sorted(set(blockers + contract["blockers"]))
    findings = list({item["id"]: item for item in contract["review"]["findings"]}.values())
    findings.sort(key=lambda item: item["id"])
    result = {
        "schema": SCHEMA, "binding": expected_binding,
        "status": "incomplete" if blockers else contract["status"],
        "blockers": blockers, "findings": findings,
        "review_identity": {
            "review_id": contract["review"]["review_id"],
            "head_sha": expected_binding["head_sha"],
            "app_id": configured.get("app_id"),
            "account_id": configured.get("account_id"),
            "login": review.PULLFROG_LOGIN,
        },
        "review_output_digest": contract["review"]["output_digest"],
        "contract_evidence_digest": contract["evidence_digest"],
        "threads": contract["threads"],
        "raw_text_included": False,
    }
    result["evidence_digest"] = digest(result)
    return result
