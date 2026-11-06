#!/usr/bin/env python3
"""Bind a trusted Speculoos run to one PR revision; never publish a check.

The producer runs only from the default-branch checkout. The verifier runs in a
separate trusted host after downloading an existing GitHub artifact. Neither
entry point discovers credentials, changes settings, or writes to GitHub.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import re
import stat
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

REPO = "fr-meyer/agent-toolkit"
WORKFLOW_PATH = ".github/workflows/speculoos-trusted-canary.yml"
SCHEMA = "agent-toolkit-speculoos-run-binding.v1"
CHECK_NAME = "speculoos-exact-head"
SHA = re.compile(r"[0-9a-f]{40}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_ARCHIVE = 4_000_000
MAX_MEMBER = 2_000_000
MAX_RUN_AGE_SECONDS = 3600
REQUIRED_CHECKS = frozenset({
    "exact_git_identity", "task_identity", "per_pr_packet_changed", "changed_files_match",
    "release_policy_wording", "task_reference", "documentation_impact",
    "workflow_materialization", "actor_policy", "diff_check", "private_data_scan",
})


class EvidenceError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _strict_json(raw: bytes) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError("duplicate_json_key")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(EvidenceError("nonfinite_json")))
    except (UnicodeError, ValueError) as exc:
        raise EvidenceError("invalid_json") from exc
    if not isinstance(value, dict):
        raise EvidenceError("invalid_json_root")
    return value


def _valid_identity(binding: dict[str, Any]) -> bool:
    integers = ("repository_id", "pr_number", "run_id", "run_attempt")
    return (
        binding.get("repository") == REPO
        and all(type(binding.get(key)) is int and binding[key] > 0 for key in integers)
        and all(isinstance(binding.get(key), str) and SHA.fullmatch(binding[key])
                for key in ("head_sha", "base_sha", "source_sha"))
        and binding.get("base_ref") == "dev"
        and isinstance(binding.get("head_ref"), str)
        and binding["head_ref"].startswith(("feat/", "fix/", "docs/", "test/", "chore/"))
        and isinstance(binding.get("task"), str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", binding["task"]) is not None
        and isinstance(binding.get("report_sha256"), str)
        and HEX.fullmatch(binding["report_sha256"]) is not None
    )


def produce(report_raw: bytes, *, repository_id: int, pr_number: int, head_ref: str,
            head_sha: str, base_ref: str, base_sha: str, source_sha: str,
            run_id: int, run_attempt: int) -> dict[str, Any]:
    report = _strict_json(report_raw)
    if (report.get("schema") != "agent-toolkit-speculoos-pr-contract/v1"
            or report.get("status") != "ok" or report.get("blockers") != []
            or report.get("task_source") != "per-pr"
            or not isinstance(report.get("checks"), list)
            or len(report["checks"]) != len(REQUIRED_CHECKS)
            or {row.get("name") for row in report["checks"] if isinstance(row, dict)} != REQUIRED_CHECKS
            or any(not isinstance(row, dict) or row.get("status") != "passed" for row in report["checks"])):
        raise EvidenceError("speculoos_contract_not_clean")
    binding = {
        "repository": REPO, "repository_id": repository_id, "pr_number": pr_number,
        "head_ref": head_ref, "head_sha": head_sha,
        "base_ref": base_ref, "base_sha": base_sha,
        "source_sha": source_sha, "run_id": run_id, "run_attempt": run_attempt,
        "task": report.get("task"), "report_sha256": hashlib.sha256(report_raw).hexdigest(),
    }
    if not _valid_identity(binding):
        raise EvidenceError("invalid_run_binding_identity")
    if any(report.get(key) != binding[value] for key, value in (
        ("repository", "repository"), ("head_ref", "head_ref"), ("head_sha", "head_sha"),
        ("base_ref", "base_ref"), ("base_sha", "base_sha"), ("task", "task"))):
        raise EvidenceError("contract_revision_mismatch")
    return {"schema": SCHEMA, "binding": binding, "binding_digest": _digest(binding)}


def _timestamp(value: Any) -> float:
    if not isinstance(value, str):
        raise EvidenceError("invalid_run_timestamp")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.timestamp()
    except (ValueError, OverflowError) as exc:
        raise EvidenceError("invalid_run_timestamp") from exc


def _archive_members(raw: bytes) -> tuple[bytes, bytes]:
    if len(raw) > MAX_ARCHIVE:
        raise EvidenceError("artifact_oversized")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            rows = archive.infolist()
            if (len(rows) != 2 or {row.filename for row in rows} != {"contract.json", "attestation.json"}
                    or any(row.file_size > MAX_MEMBER or row.flag_bits & 1
                           or stat.S_ISLNK(row.external_attr >> 16) for row in rows)):
                raise EvidenceError("artifact_members_invalid")
            result = []
            for name in ("contract.json", "attestation.json"):
                with archive.open(name) as member:
                    content = member.read(MAX_MEMBER + 1)
                if len(content) > MAX_MEMBER:
                    raise EvidenceError("artifact_member_oversized")
                result.append(content)
            return result[0], result[1]
    except EvidenceError:
        raise
    except (zipfile.BadZipFile, RuntimeError, ValueError) as exc:
        raise EvidenceError("artifact_archive_invalid") from exc


def verify_source_bundle(raw: bytes, *, artifact: dict[str, Any], run: dict[str, Any],
                         pr: dict[str, Any], repository_id: int,
                         expected_source_sha: str, now: float) -> dict[str, Any]:
    report_raw, attestation_raw = _archive_members(raw)
    attestation = _strict_json(attestation_raw)
    binding = attestation.get("binding")
    if (attestation.get("schema") != SCHEMA or not isinstance(binding, dict)
            or not _valid_identity(binding) or attestation.get("binding_digest") != _digest(binding)
            or binding["repository_id"] != repository_id
            or binding["source_sha"] != expected_source_sha
            or binding["report_sha256"] != hashlib.sha256(report_raw).hexdigest()):
        raise EvidenceError("attestation_binding_invalid")
    expected = produce(report_raw, repository_id=repository_id, pr_number=binding["pr_number"],
                       head_ref=binding["head_ref"], head_sha=binding["head_sha"],
                       base_ref=binding["base_ref"], base_sha=binding["base_sha"],
                       source_sha=binding["source_sha"], run_id=binding["run_id"],
                       run_attempt=binding["run_attempt"])
    if attestation != expected:
        raise EvidenceError("attestation_report_mismatch")
    repo = run.get("repository") if isinstance(run.get("repository"), dict) else {}
    if (type(run.get("id")) is not int or run["id"] != binding["run_id"]
            or type(run.get("run_attempt")) is not int or run["run_attempt"] != binding["run_attempt"]
            or run.get("event") != "pull_request_target"
            or run.get("path") not in (WORKFLOW_PATH, WORKFLOW_PATH + "@main")
            or run.get("head_sha") != binding["source_sha"] or run.get("head_branch") != "main"
            or run.get("status") != "completed" or run.get("conclusion") != "success"
            or type(repo.get("id")) is not int or repo["id"] != repository_id
            or repo.get("full_name") != REPO):
        raise EvidenceError("workflow_run_untrusted")
    created = _timestamp(run.get("created_at"))
    started, completed = _timestamp(run.get("run_started_at")), _timestamp(run.get("updated_at"))
    if not (created <= started <= completed
            and completed - started <= MAX_RUN_AGE_SECONDS
            and 0 <= now - completed <= MAX_RUN_AGE_SECONDS):
        raise EvidenceError("workflow_run_stale")
    artifact_run = artifact.get("workflow_run") if isinstance(artifact.get("workflow_run"), dict) else {}
    if (type(artifact.get("id")) is not int or artifact["id"] < 1
            or artifact.get("name") != (f"speculoos-pr-{binding['pr_number']}-{binding['head_sha']}"
                                        f"-{binding['run_id']}-{binding['run_attempt']}")
            or artifact.get("expired") is not False
            or artifact.get("digest") != "sha256:" + hashlib.sha256(raw).hexdigest()
            or type(artifact_run.get("id")) is not int or artifact_run["id"] != binding["run_id"]
            or type(artifact_run.get("repository_id")) is not int or artifact_run["repository_id"] != repository_id
            or type(artifact_run.get("head_repository_id")) is not int
            or artifact_run["head_repository_id"] != repository_id
            or artifact_run.get("head_branch") != "main"
            or artifact_run.get("head_sha") != binding["source_sha"]):
        raise EvidenceError("artifact_provenance_invalid")
    if _timestamp(artifact.get("expires_at")) <= now:
        raise EvidenceError("artifact_expired")
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    if (type(pr.get("number")) is not int or pr["number"] != binding["pr_number"]
            or pr.get("state") != "open"
            or head.get("ref") != binding["head_ref"] or head.get("sha") != binding["head_sha"]
            or base.get("ref") != binding["base_ref"] or base.get("sha") != binding["base_sha"]
            or type(head_repo.get("id")) is not int or head_repo["id"] != repository_id
            or type(base_repo.get("id")) is not int or base_repo["id"] != repository_id):
        raise EvidenceError("live_pr_revision_drift")
    return {"schema": SCHEMA, "status": "source_verified", "repository": REPO,
            "pr_number": binding["pr_number"], "head_sha": binding["head_sha"],
            "base_sha": binding["base_sha"], "source_sha": binding["source_sha"],
            "run_id": binding["run_id"], "run_attempt": binding["run_attempt"],
            "artifact_id": artifact["id"], "binding_digest": attestation["binding_digest"]}


def prepare_head_check_intent(raw: bytes, *, artifact: dict[str, Any], run: dict[str, Any],
                              pr: dict[str, Any], repository_id: int,
                              expected_source_sha: str, now: float) -> dict[str, Any]:
    """Reverify source in-process before preparing data for an App publisher."""
    source = verify_source_bundle(raw, artifact=artifact, run=run, pr=pr,
                                  repository_id=repository_id,
                                  expected_source_sha=expected_source_sha, now=now)
    return {"name": CHECK_NAME, "head_sha": source["head_sha"],
            "status": "completed", "conclusion": "success",
            "external_id": "speculoos:v1:" + source["binding_digest"]}


def verify_archive(raw: bytes, *, artifact: dict[str, Any], run: dict[str, Any],
                   check: dict[str, Any], pr: dict[str, Any], repository_id: int,
                   trusted_app_id: int, expected_source_sha: str, now: float) -> dict[str, Any]:
    source = verify_source_bundle(raw, artifact=artifact, run=run, pr=pr,
                                  repository_id=repository_id,
                                  expected_source_sha=expected_source_sha, now=now)
    app = check.get("app") if isinstance(check.get("app"), dict) else {}
    if (type(trusted_app_id) is not int or trusted_app_id < 1
            or type(check.get("id")) is not int or check["id"] < 1
            or check.get("name") != CHECK_NAME or check.get("head_sha") != source["head_sha"]
            or check.get("status") != "completed" or check.get("conclusion") != "success"
            or check.get("external_id") != "speculoos:v1:" + source["binding_digest"]
            or type(app.get("id")) is not int or app["id"] != trusted_app_id):
        raise EvidenceError("trusted_head_check_missing")
    return {**source, "status": "verified", "check_run_id": check["id"]}


def collect_verified(client, download, *, pr_number: int, run_id: int,
                     artifact_id: int, repository_id: int, trusted_app_id: int,
                     expected_source_sha: str, now: float) -> dict[str, Any]:
    """Read an existing run/artifact/check through an injected trusted client.

    The downloader must independently constrain redirects, archive size and
    credential forwarding. This function never creates a check or a run.
    """
    if any(type(value) is not int or value < 1 for value in
           (pr_number, run_id, artifact_id, repository_id, trusted_app_id)):
        raise EvidenceError("invalid_collection_identity")
    started_monotonic = time.monotonic()
    prefix = "/repos/" + REPO
    first = client.get(f"{prefix}/pulls/{pr_number}")
    head = first.get("head") if isinstance(first, dict) and isinstance(first.get("head"), dict) else {}
    head_sha = head.get("sha")
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise EvidenceError("invalid_live_pr_head")
    run = client.get(f"{prefix}/actions/runs/{run_id}")
    artifact = client.get(f"{prefix}/actions/artifacts/{artifact_id}")
    raw = download(artifact_id)
    if not isinstance(raw, bytes) or len(raw) > MAX_ARCHIVE:
        raise EvidenceError("artifact_download_invalid")
    _, attestation_raw = _archive_members(raw)
    attestation = _strict_json(attestation_raw)
    binding = attestation.get("binding") if isinstance(attestation.get("binding"), dict) else {}
    if binding.get("head_sha") != head_sha:
        raise EvidenceError("artifact_head_not_current")
    collection = client.get(f"{prefix}/commits/{head_sha}/check-runs?per_page=100")
    checks = collection.get("check_runs") if isinstance(collection, dict) else None
    total = collection.get("total_count") if isinstance(collection, dict) else None
    if (not isinstance(checks, list) or type(total) is not int or total != len(checks)):
        raise EvidenceError("head_check_collection_incomplete")
    matches = [check for check in checks if isinstance(check, dict)
               and check.get("name") == CHECK_NAME
               and isinstance(check.get("app"), dict)
               and check["app"].get("id") == trusted_app_id]
    if len(matches) != 1:
        raise EvidenceError("head_check_ambiguous_or_missing")
    receipt = verify_archive(raw, artifact=artifact, run=run, check=matches[0],
                             pr=first, repository_id=repository_id,
                             trusted_app_id=trusted_app_id,
                             expected_source_sha=expected_source_sha, now=now)
    latest = client.get(f"{prefix}/pulls/{pr_number}")
    if (not isinstance(latest, dict) or latest.get("number") != pr_number
            or latest.get("state") != "open" or latest.get("head") != first.get("head")
            or latest.get("base") != first.get("base")):
        raise EvidenceError("live_pr_changed_during_evidence_collection")
    final_run = client.get(f"{prefix}/actions/runs/{run_id}")
    final_artifact = client.get(f"{prefix}/actions/artifacts/{artifact_id}")
    final_collection = client.get(f"{prefix}/commits/{head_sha}/check-runs?per_page=100")
    if (final_run != run or final_artifact != artifact or final_collection != collection):
        raise EvidenceError("evidence_changed_during_collection")
    final_pr = client.get(f"{prefix}/pulls/{pr_number}")
    if (not isinstance(final_pr, dict) or final_pr.get("number") != pr_number
            or final_pr.get("state") != "open" or final_pr.get("head") != first.get("head")
            or final_pr.get("base") != first.get("base")):
        raise EvidenceError("live_pr_changed_during_evidence_collection")
    finished_now = now + max(0.0, time.monotonic() - started_monotonic)
    final_receipt = verify_archive(raw, artifact=final_artifact, run=final_run,
                                   check=matches[0], pr=final_pr, repository_id=repository_id,
                                   trusted_app_id=trusted_app_id,
                                   expected_source_sha=expected_source_sha, now=finished_now)
    if final_receipt != receipt:
        raise EvidenceError("evidence_changed_during_collection")
    return final_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repository-id", type=int, required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    args = parser.parse_args(argv)
    raw = Path(args.report).read_bytes()
    result = produce(raw, repository_id=args.repository_id, pr_number=args.pr_number,
                     head_ref=args.head_ref, head_sha=args.head_sha,
                     base_ref=args.base_ref, base_sha=args.base_sha,
                     source_sha=args.source_sha, run_id=args.run_id, run_attempt=args.run_attempt)
    output = Path(args.output)
    if output != Path("artifacts/speculoos/attestation.json"):
        raise EvidenceError("untrusted_attestation_output")
    output.write_bytes(_canonical(result) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
