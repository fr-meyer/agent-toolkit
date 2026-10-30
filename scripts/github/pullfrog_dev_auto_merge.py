#!/usr/bin/env python3
"""Fail-closed exact-head auto-merge for clean non-stable feature PRs.

The irreversible boundary is a normal fast-forward Git receive-pack update of
a locally built two-parent merge commit. The command binds the literal reviewed
base ref and its exact reviewed tip as the old OID in the server's ref
transaction; GitHub's pull-request merge endpoint cannot express either base
predicate. Targets named ``main`` or ``master`` always fail closed.
"""

from __future__ import annotations

import argparse
import base64
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
import pullfrog_review_contract as review_contract  # noqa: E402

RECEIPT_SCHEMA = "pullfrog-auto-merge-receipt.v1"
COORDINATOR_SCHEMA = "pullfrog-cloud-coordinator-receipt.v1"
FORBIDDEN_BASE_REFS = frozenset({"main", "master"})
DEV_AUTOMATION_REF = "dev"
ALLOWED_HEAD_PREFIXES = ("feat/", "fix/", "docs/", "test/", "chore/")
COORDINATOR_REQUIRED_CHECKS = cycle_contract.REQUIRED_CHECKS
MERGE_REQUIRED_CHECKS = frozenset(
    {review_contract.GATE_NAME, "ci", "speculoos", "destination-guard"}
)
# Backward-compatible alias for tests and receipt fixtures describing the
# coordinator cycle contract rather than the fresh merge boundary.
REQUIRED_CHECKS = COORDINATOR_REQUIRED_CHECKS
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_GIT_PROTOCOL_BYTES = 8 * 1024 * 1024
MAX_PUSH_PACK_BYTES = 64 * 1024 * 1024
GIT_PUSH_AGENT = "agent-toolkit-pullfrog-auto-merge/1"
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
    identity = review_contract.normalize_identity(value)
    head_ref = identity["head_ref"]
    if (
        not review_contract._valid_gate_identity(identity)
        or identity["base_ref"] in FORBIDDEN_BASE_REFS
        or not any(
            head_ref.startswith(prefix) and len(head_ref) > len(prefix)
            for prefix in ALLOWED_HEAD_PREFIXES
        )
    ):
        raise AutoMergeError("ineligible_identity")
    if _text(_mapping(value).get("identity_digest")) != review_contract.identity_digest(
        identity
    ):
        raise AutoMergeError("invalid_identity_digest")
    return identity


def _validated_receipt_check_rules(
    receipt: dict[str, Any], identity: dict[str, Any]
) -> dict[str, list[tuple[str, str]]]:
    details = _mapping(receipt.get("checks"))
    if not {"pullfrog_review_gate", "ci", "speculoos"}.issubset(details):
        raise AutoMergeError("invalid_receipt_check_details")
    contract = _mapping(receipt.get("review_contract"))
    evidence_profile = _text(contract.get("evidence_profile"))
    evidence_digest = _text(contract.get("evidence_digest"))
    try:
        expected_gate_external_id = review_contract.gate_external_id(
            identity,
            evidence_profile,
            evidence_digest,
        )
    except review_contract.ReviewContractError as exc:
        raise AutoMergeError("invalid_receipt_check_details") from exc
    gate = _mapping(details.get("pullfrog_review_gate"))
    if (
        coordinator._check_rule(gate)
        != (review_contract.GATE_NAME, review_contract.GATE_APP)
        or gate.get("status") != "success"
        or gate.get("head_sha") != identity["head_sha"]
        or (_integer(gate.get("check_run_id")) or 0) < 1
        or gate.get("external_id") != expected_gate_external_id
        or gate.get("evidence_profile") != evidence_profile
        or gate.get("evidence_digest") != evidence_digest
    ):
        raise AutoMergeError("invalid_receipt_check_details")
    rules: dict[str, list[tuple[str, str]]] = {}
    for group in ("ci", "speculoos"):
        values = details.get(group) if isinstance(details.get(group), list) else []
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
    authority = _mapping(receipt.get("authority_decision"))
    policy_decision = _mapping(receipt.get("policy_decision"))
    author = _mapping(_mapping(authority.get("identity")).get("author"))
    policy = _mapping(authority.get("policy"))
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
        or repository.get("base_repository_slug") != identity["base_repository_slug"]
        or repository.get("author_login") != identity["author_login"]
        or repository.get("author_account_id") != identity["author_account_id"]
        or repository.get("author_type") != identity["author_type"]
        or repository.get("trusted_author_policy_schema")
        != identity["trusted_author_policy_schema"]
        or repository.get("trusted_author_policy_digest")
        != identity["trusted_author_policy_digest"]
        or repository.get("identity_digest") != review_contract.identity_digest(identity)
        or authority.get("review_eligible") is not True
        or authority.get("same_repository") is not True
        or authority.get("trusted_author") is not True
        or authority.get("mutation_authorized") is not True
        or author.get("login") != identity["author_login"]
        or author.get("account_id") != identity["author_account_id"]
        or author.get("type") != identity["author_type"]
        or policy.get("schema") != identity["trusted_author_policy_schema"]
        or policy.get("digest") != identity["trusted_author_policy_digest"]
        or policy_decision.get("mutation_authorized") is not True
        or policy_decision.get("merge_allowed") is not True
        or policy_decision.get("manual_governance_required") is not False
        or _mapping(receipt.get("identity")).get("event_head_sha") != identity["head_sha"]
        or event.get("head_sha") != identity["head_sha"]
        or review.get("head_sha") != identity["head_sha"]
        or _integer(review.get("finding_count")) != 0
        or required_checks != sorted(COORDINATOR_REQUIRED_CHECKS)
        or set(observed_checks) != COORDINATOR_REQUIRED_CHECKS
        or evidence.get("missing_checks") != []
    ):
        raise AutoMergeError("invalid_clean_decision")
    for name in COORDINATOR_REQUIRED_CHECKS:
        check = _mapping(observed_checks.get(name))
        if check.get("status") != "success" or check.get("head_sha") != identity["head_sha"]:
            raise AutoMergeError("required_evidence_not_successful")

    contract = _mapping(receipt.get("review_contract"))
    contract_identity = review_contract.normalize_identity(contract.get("identity"))
    expected_contract_identity = review_contract.normalize_identity(identity)
    contract_review = _mapping(contract.get("review"))
    contract_threads = _mapping(contract.get("threads"))
    contract_gate = _mapping(contract.get("gate"))
    evidence_profile = _text(contract.get("evidence_profile"))
    evidence_digest = _text(contract.get("evidence_digest"))
    try:
        expected_gate_external_id = review_contract.gate_external_id(
            contract_identity,
            evidence_profile,
            evidence_digest,
        )
    except review_contract.ReviewContractError as exc:
        raise AutoMergeError("invalid_review_contract") from exc
    if (
        contract.get("schema") != review_contract.CONTRACT_SCHEMA
        or contract.get("status") != "clean"
        or contract.get("blockers") != []
        or contract_identity != expected_contract_identity
        or str(_integer(contract_review.get("review_id")) or 0)
        != _text(review.get("review_id"))
        or _integer(contract_review.get("finding_count")) != 0
        or _integer(contract_threads.get("unresolved_pullfrog_count")) != 0
        or contract_gate.get("name") != review_contract.GATE_NAME
        or contract_gate.get("app_slug") != review_contract.GATE_APP
        or contract_gate.get("external_id") != expected_gate_external_id
        or contract_gate.get("conclusion") != "success"
    ):
        raise AutoMergeError("invalid_review_contract")

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
    try:
        observed = review_contract.identity_from_pull_request(
            identity["repository_slug"], pr
        )
    except review_contract.trusted_author_policy.TrustedAuthorPolicyError as exc:
        raise AutoMergeError("live_pull_request_identity_invalid") from exc
    if (
        pr.get("state") != "open"
        or pr.get("draft") is True
        or observed != identity
        or observed["base_ref"] in FORBIDDEN_BASE_REFS
    ):
        raise AutoMergeError("live_pull_request_drift")


def _refresh_exact_head_evidence(
    client: "GitHubMergeClient",
    receipt: dict[str, Any],
    identity: dict[str, Any],
    *,
    repository: dict[str, Any],
    changed_paths: list[str],
    reviews: list[Any],
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
    for group in ("ci", "speculoos"):
        selected[group] = [
            coordinator._select_check(check_runs, identity["head_sha"], name, app_slug)
            for name, app_slug in rules[group]
        ]
        if any(item.get("status") != "success" for item in selected[group]):
            raise AutoMergeError("fresh_required_evidence_not_successful")
        if any(item.get("spoofed_count") or item.get("stale_count") for item in selected[group]):
            raise AutoMergeError("fresh_required_evidence_ambiguous")

    comments = client.paginated(
        f"{prefix}/pulls/{identity['pr_number']}/comments"
    )
    try:
        review_threads = review_contract.collect_review_threads(client, identity)
    except review_contract.ReviewContractError as exc:
        raise AutoMergeError("fresh_review_contract_collection_failed") from exc
    contract_snapshot = {
        "schema": review_contract.SNAPSHOT_SCHEMA,
        "expected_identity": identity,
        "observed_identity": identity,
        "reviews": reviews,
        "review_comments": comments,
        "review_threads": review_threads,
        "check_runs": check_runs,
    }
    contracts = [
        review_contract.evaluate_contract(contract_snapshot),
        review_contract.evaluate_contract(
            contract_snapshot,
            review_contract.REVIEW_ONLY_EVIDENCE_PROFILE,
        ),
    ]
    gate = review_contract.select_gate(check_runs, identity, contracts)
    if (
        gate.get("spoofed_count")
        or gate.get("stale_count")
        or gate.get("external_id_mismatch")
    ):
        raise AutoMergeError("fresh_pullfrog_review_gate_ambiguous")
    if gate.get("status") != "success" or gate.get("contract_status") != "clean":
        raise AutoMergeError("fresh_pullfrog_review_gate_not_successful")

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
        "pullfrog_review_gate_id": gate.get("check_run_id"),
        "pullfrog_review_gate_external_id": gate.get("external_id"),
        "pullfrog_review_evidence_profile": gate.get("evidence_profile"),
        "pullfrog_review_evidence_digest": gate.get("evidence_digest"),
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

    @staticmethod
    def _pkt_line(payload: bytes) -> bytes:
        length = len(payload) + 4
        if length > 0xFFFF:
            raise AutoMergeError("git_protocol_packet_too_large")
        return f"{length:04x}".encode("ascii") + payload

    @staticmethod
    def _pkt_payloads(data: bytes) -> list[bytes | None]:
        packets: list[bytes | None] = []
        offset = 0
        while offset < len(data):
            if offset + 4 > len(data):
                raise AutoMergeError("invalid_git_protocol_response")
            prefix = data[offset : offset + 4]
            try:
                length = int(prefix, 16)
            except ValueError as exc:
                raise AutoMergeError("invalid_git_protocol_response") from exc
            offset += 4
            if length in {0, 1, 2}:
                packets.append(None)
                continue
            if length < 4 or offset + length - 4 > len(data):
                raise AutoMergeError("invalid_git_protocol_response")
            packets.append(data[offset : offset + length - 4])
            offset += length - 4
        return packets

    @staticmethod
    def _basic_git_authorization(token: str) -> str:
        if not token:
            raise AutoMergeError("missing_github_token")
        encoded = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode(
            "ascii"
        )
        return f"Basic {encoded}"

    @staticmethod
    def _bounded_protocol_output(data: bytes) -> bytes:
        if len(data) > MAX_GIT_PROTOCOL_BYTES:
            raise AutoMergeError("git_protocol_response_too_large")
        return data

    def _receive_pack_advertisement(self, remote: str, token: str) -> bytes:
        parsed = urllib.parse.urlparse(remote)
        if parsed.scheme in {"http", "https"}:
            url = remote.rstrip("/") + "/info/refs?service=git-receive-pack"
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/x-git-receive-pack-advertisement",
                    "Authorization": self._basic_git_authorization(token),
                    "User-Agent": GIT_PUSH_AGENT,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read(MAX_GIT_PROTOCOL_BYTES + 1)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                raise AutoMergeError("git_receive_pack_advertisement_failed") from exc
            return self._bounded_protocol_output(data)
        try:
            result = subprocess.run(
                ["git", "receive-pack", "--stateless-rpc", "--advertise-refs", remote],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AutoMergeError("git_receive_pack_advertisement_failed") from exc
        if result.returncode != 0:
            raise AutoMergeError("git_receive_pack_advertisement_failed")
        return self._bounded_protocol_output(result.stdout)

    def _submit_receive_pack(self, remote: str, token: str, body: bytes) -> bytes:
        parsed = urllib.parse.urlparse(remote)
        if parsed.scheme in {"http", "https"}:
            request = urllib.request.Request(
                remote.rstrip("/") + "/git-receive-pack",
                data=body,
                method="POST",
                headers={
                    "Accept": "application/x-git-receive-pack-result",
                    "Authorization": self._basic_git_authorization(token),
                    "Content-Type": "application/x-git-receive-pack-request",
                    "User-Agent": GIT_PUSH_AGENT,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = response.read(MAX_GIT_PROTOCOL_BYTES + 1)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                raise AutoMergeError("base_compare_and_swap_failed") from exc
            return self._bounded_protocol_output(data)
        try:
            result = subprocess.run(
                ["git", "receive-pack", "--stateless-rpc", remote],
                input=body,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AutoMergeError("base_compare_and_swap_failed") from exc
        if result.returncode != 0:
            raise AutoMergeError("base_compare_and_swap_failed")
        return self._bounded_protocol_output(result.stdout)

    @classmethod
    def _advertised_ref(cls, data: bytes, ref: str) -> tuple[str, set[str]]:
        advertised: dict[bytes, str] = {}
        capabilities: set[str] = set()
        for payload in cls._pkt_payloads(data):
            if payload is None or payload.startswith(b"# service="):
                continue
            line = payload.rstrip(b"\n")
            if line.startswith(b"version "):
                continue
            if b"\0" in line:
                line, raw_capabilities = line.split(b"\0", 1)
                try:
                    capabilities = set(raw_capabilities.decode("ascii").split())
                except UnicodeDecodeError as exc:
                    raise AutoMergeError("invalid_git_protocol_advertisement") from exc
            fields = line.split(b" ", 1)
            if len(fields) != 2:
                raise AutoMergeError("invalid_git_protocol_advertisement")
            raw_oid, raw_ref = fields
            try:
                oid = raw_oid.decode("ascii")
            except UnicodeDecodeError as exc:
                raise AutoMergeError("invalid_git_protocol_advertisement") from exc
            if SHA_RE.fullmatch(oid):
                advertised[raw_ref] = oid
        old_oid = advertised.get(ref.encode("utf-8"))
        if old_oid is None:
            raise AutoMergeError("base_compare_and_swap_failed")
        if not ({"report-status", "side-band-64k"} <= capabilities):
            raise AutoMergeError("unsupported_git_receive_pack_capabilities")
        if any(
            value.startswith("object-format=") and value != "object-format=sha1"
            for value in capabilities
        ):
            raise AutoMergeError("unsupported_git_object_format")
        return old_oid, capabilities

    @staticmethod
    def _pack_objects(workspace: Path, new_oid: str, old_oid: str) -> bytes:
        try:
            result = subprocess.run(
                [
                    "git",
                    "pack-objects",
                    "--stdout",
                    "--revs",
                    "--thin",
                    "--delta-base-offset",
                ],
                cwd=workspace,
                input=f"{new_oid}\n^{old_oid}\n".encode("ascii"),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AutoMergeError("git_pack_creation_failed") from exc
        if (
            result.returncode != 0
            or not result.stdout.startswith(b"PACK")
            or len(result.stdout) > MAX_PUSH_PACK_BYTES
        ):
            raise AutoMergeError("git_pack_creation_failed")
        return result.stdout

    @classmethod
    def _receive_pack_body(
        cls,
        *,
        old_oid: str,
        new_oid: str,
        ref: str,
        capabilities: set[str],
        pack: bytes,
    ) -> bytes:
        report_capability = (
            "report-status-v2" if "report-status-v2" in capabilities else "report-status"
        )
        requested = [report_capability, "side-band-64k", "ofs-delta", f"agent={GIT_PUSH_AGENT}"]
        if "object-format=sha1" in capabilities:
            requested.append("object-format=sha1")
        command = f"{old_oid} {new_oid} {ref}\0{' '.join(requested)}\n".encode("ascii")
        return cls._pkt_line(command) + b"0000" + pack

    @classmethod
    def _assert_receive_pack_success(cls, data: bytes, ref: str) -> None:
        channel_one = bytearray()
        for payload in cls._pkt_payloads(data):
            if payload is None:
                continue
            if payload[:1] == b"\x03":
                raise AutoMergeError("base_compare_and_swap_failed")
            if payload[:1] == b"\x01":
                channel_one.extend(payload[1:])
            elif payload[:1] != b"\x02":
                channel_one.extend(payload)
        status_data = bytes(channel_one)
        try:
            nested = cls._pkt_payloads(status_data)
        except AutoMergeError:
            nested = [line + b"\n" for line in status_data.splitlines()]
        lines = {
            payload.decode("utf-8", "replace").strip()
            for payload in nested
            if payload is not None and payload.strip()
        }
        if "unpack ok" not in lines or f"ok {ref}" not in lines:
            raise AutoMergeError("base_compare_and_swap_failed")
        if any(line.startswith("ng ") for line in lines):
            raise AutoMergeError("base_compare_and_swap_failed")

    def _repository_remote(self) -> str:
        return f"https://github.com/{self.repository_slug}.git"

    def push_exact_merge(self, identity: dict[str, Any], title: str) -> dict[str, Any]:
        """Build and normally push one merge commit onto the reviewed base.

        The generated commit's first parent is the reviewed base SHA. The Git
        receive-pack command carries that exact SHA as the update's old OID, so
        the server rejects any intervening base change in the same ref-update
        transaction. The update remains a normal fast-forward, never a force or
        force-with-lease, and targets the literal reviewed base ref.
        """

        token = self.token
        if not token:
            raise AutoMergeError("missing_github_token")
        _assert_live_pull_request(
            _mapping(
                self.get(f"{self.allowed_prefix}/pulls/{identity['pr_number']}")
            ),
            identity,
        )
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
            destination = f"refs/heads/{identity['base_ref']}"
            advertisement = self._receive_pack_advertisement(remote, token)
            advertised_old, capabilities = self._advertised_ref(
                advertisement, destination
            )
            if advertised_old != identity["base_sha"]:
                raise AutoMergeError("base_compare_and_swap_failed")
            pack = self._pack_objects(workspace, merge_sha, identity["base_sha"])
            _assert_live_pull_request(
                _mapping(
                    self.get(
                        f"{self.allowed_prefix}/pulls/{identity['pr_number']}"
                    )
                ),
                identity,
            )
            response = self._submit_receive_pack(
                remote,
                token,
                self._receive_pack_body(
                    old_oid=identity["base_sha"],
                    new_oid=merge_sha,
                    ref=destination,
                    capabilities=capabilities,
                    pack=pack,
                ),
            )
            self._assert_receive_pack_success(response, destination)
        return {
            "merged": True,
            "sha": merge_sha,
            "base_ref": identity["base_ref"],
            "base_sha": identity["base_sha"],
            "head_sha": identity["head_sha"],
            "transport": "exact-old-oid-normal-fast-forward-push",
        }

    def dispatch_workflow(
        self,
        workflow: str,
        *,
        ref: str,
        inputs: dict[str, str],
    ) -> None:
        if workflow not in ALLOWED_DISPATCH_WORKFLOWS or ref != DEV_AUTOMATION_REF:
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
                "User-Agent": "agent-toolkit-pullfrog-auto-merge",
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
    # These manual dispatches replace dev push events suppressed by GITHUB_TOKEN.
    # Other eligible integration branches must not publish unintegrated workflow
    # assets through dev's downstream automation.
    if identity["base_ref"] != DEV_AUTOMATION_REF:
        return [], []

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


def merge_clean_pr(
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
        changed_paths=changed_paths,
        reviews=reviews,
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
        or merge.get("transport") != "exact-old-oid-normal-fast-forward-push"
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
        "identity_digest": review_contract.identity_digest(identity),
        "author_login": identity["author_login"],
        "author_account_id": identity["author_account_id"],
        "author_type": identity["author_type"],
        "trusted_author_policy_schema": identity[
            "trusted_author_policy_schema"
        ],
        "trusted_author_policy_digest": identity[
            "trusted_author_policy_digest"
        ],
        "merge_commit_sha": merge_sha,
        "merge_method": "merge",
        "merge_transport": "exact-old-oid-normal-fast-forward-push",
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
        result = merge_clean_pr(
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
        raise SystemExit(f"auto-merge failed: {code}") from exc
    _write_object(Path(args.out), result)
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "merged":
        raise SystemExit("auto-merge completed with downstream dispatch failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
