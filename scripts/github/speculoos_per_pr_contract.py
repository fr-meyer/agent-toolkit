#!/usr/bin/env python3
"""Zero-secret hosted validation for this repository's Speculoos PR contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TASK_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
REQUIRED_EVIDENCE = {
    "pullfrog",
    "pullfrog-approval",
    "ci",
    "speculoos",
    "destination-guard",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "literal_bearer": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b"),
    "credentialed_url": re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"),
}
PER_PR_GOVERNED_PREFIXES = (
    ".speculoos/",
    ".github/",
    "templates/",
    "scripts/github/",
)
MAX_SCANNED_FILE_BYTES = 2_000_000


class ContractError(RuntimeError):
    pass


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _git_bytes(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _head_blob(repo: Path, relative: str) -> bytes | None:
    entries = _git_bytes(
        repo, "--literal-pathspecs", "ls-tree", "-r", "-z", "HEAD", "--", relative
    ).stdout
    matching = []
    for entry in entries.split(b"\x00"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        if path == relative.encode("utf-8"):
            matching.append(metadata.split())
    if not matching:
        return None
    if len(matching) != 1 or matching[0][0] not in {b"100644", b"100755"}:
        raise ContractError(f"missing or unsafe file: {relative}")
    blob_sha = matching[0][2].decode("ascii")
    size = int(_git(repo, "cat-file", "-s", blob_sha).stdout.strip())
    if size > MAX_SCANNED_FILE_BYTES:
        raise ContractError(f"oversized file: {relative}")
    return _git_bytes(repo, "cat-file", "blob", blob_sha).stdout


def _regular_text(repo: Path, relative: str) -> str:
    raw = _head_blob(repo, relative)
    if raw is None:
        raise ContractError(f"missing or unsafe file: {relative}")
    return raw.decode("utf-8")


def _top_level_scalar(text: str, key: str) -> str:
    matches = list(re.finditer(rf"(?m)^{re.escape(key)}:\s*([^#\n]*?)\s*$", text))
    if len(matches) != 1:
        raise ContractError(f"expected one top-level field: {key}")
    value = matches[0].group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if not value:
        raise ContractError(f"empty top-level field: {key}")
    return value


def _nested_scalar(text: str, section: str, key: str) -> str:
    section_lines = list(re.finditer(rf"(?m)^{re.escape(section)}:[ \t]*$", text))
    if len(section_lines) != 1:
        raise ContractError(f"expected one section: {section}")
    start = section_lines[0].end()
    indented = re.match(r"(?:\n[ \t]+[^\n]*)*", text[start:])
    body = indented.group(0) if indented else ""
    matches = list(re.finditer(rf"(?m)^  {re.escape(key)}:\s*([^#\n]*?)\s*$", body))
    if len(matches) != 1:
        raise ContractError(f"expected one field: {section}.{key}")
    value = matches[0].group(1).strip().strip("'\"")
    if not value:
        raise ContractError(f"empty field: {section}.{key}")
    return value


def _markdown_section(text: str, heading: str) -> list[str] | None:
    wanted = heading.strip().casefold()
    lines: list[str] = []
    active = False
    for line in text.splitlines():
        if line.startswith("#"):
            normalized = line.lstrip("#").strip().rstrip(":").casefold()
            if active and normalized != wanted:
                break
            if normalized == wanted:
                active = True
                continue
        elif active:
            lines.append(line)
    return lines if active else None


def _packet_changed_files(text: str) -> list[str]:
    section = _markdown_section(text, "Changed Files For Publish")
    if section is None:
        raise ContractError("publication packet lacks Changed Files For Publish")
    paths: list[str] = []
    for line in section:
        stripped = line.strip()
        if not stripped.startswith(("- ", "* ")):
            continue
        value = stripped[2:].strip().strip("`'\" ")
        if value and not value.startswith(("http://", "https://")):
            paths.append(value)
    return sorted(set(paths))


def _changed_files(repo: Path, base_ref: str) -> list[str]:
    output = _git_bytes(repo, "diff", "--no-renames", "--name-only", "-z", f"origin/{base_ref}...HEAD").stdout
    try:
        return sorted({path.decode("utf-8") for path in output.split(b"\x00") if path})
    except UnicodeDecodeError as exc:
        raise ContractError("changed path is not UTF-8") from exc


def _per_pr_task(repo: Path, base_ref: str, changed: list[str]) -> tuple[str, str]:
    """Select one newly added, PR-local task; never consult the global pointer."""
    candidates = [
        path for path in changed
        if re.fullmatch(r"specs/([A-Za-z0-9][A-Za-z0-9._-]{0,127})/task\.yaml", path)
    ]
    if len(candidates) != 1:
        raise ContractError(f"expected one changed per-PR task, found {len(candidates)}")
    path = candidates[0]
    if _git(repo, "cat-file", "-e", f"origin/{base_ref}:{path}", check=False).returncode == 0:
        raise ContractError("per-PR task must be newly added on this branch")
    task_id = path.split("/")[1]
    return task_id, path


def _added_diff(repo: Path, base_ref: str) -> str:
    raw = _git_bytes(repo, "diff", "--no-ext-diff", "--no-color", "--unified=0",
                     f"origin/{base_ref}...HEAD").stdout
    try:
        output = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("added diff is not UTF-8") from exc
    added: list[str] = []
    in_hunk = False
    for line in output.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@ "):
            in_hunk = True
        elif in_hunk and line.startswith("+"):
            added.append(line[1:])
    return "\n".join(added)


def _scan_changed_text(repo: Path, changed: list[str]) -> tuple[list[str], list[str]]:
    """Reject unscannable changed blobs instead of treating binary diffs as clean."""
    hits: set[str] = set()
    unscannable: list[str] = []
    for relative in changed:
        try:
            raw = _head_blob(repo, relative)
        except ContractError:
            unscannable.append(relative)
            continue
        if raw is None:  # Deleted files contribute no new bytes.
            continue
        if b"\x00" in raw:
            unscannable.append(relative)
            continue
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            unscannable.append(relative)
            continue
        hits.update(name for name, pattern in SECRET_PATTERNS.items() if pattern.search(content))
    return sorted(hits), unscannable


def _actor_contract(repo: Path) -> tuple[bool, str]:
    payload = json.loads(_regular_text(repo, ".speculoos/actors.json"))
    policies = payload.get("branch_policies")
    profiles = payload.get("profiles")
    if not isinstance(policies, list) or not isinstance(profiles, dict):
        return False, "actor policy shape is invalid"
    policy = next((item for item in policies if item.get("name") == "feature_to_non_stable"), None)
    profile = profiles.get("github_actions_non_stable_auto_merge")
    if not isinstance(policy, dict) or not isinstance(profile, dict):
        return False, "non-stable merge actor policy is missing"
    auto = policy.get("auto_merge")
    if not isinstance(auto, dict) or auto.get("enabled") is not True:
        return False, "non-stable auto-merge policy is not enabled"
    if set(auto.get("forbidden_base_refs") or []) != {"main", "master"}:
        return False, "stable bases are not exactly forbidden"
    if not REQUIRED_EVIDENCE.issubset(set(auto.get("required_evidence") or [])):
        return False, "required exact-head evidence is incomplete"
    if profile.get("same_repository_required") is not True or profile.get("force_push_allowed") is not False:
        return False, "merge actor repository or force-push guard is invalid"
    return True, "non-stable merge actor contract is complete"


def validate(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve()
    checks: list[dict[str, str]] = []
    blockers: list[str] = []
    task_id = args.task

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "status": "passed" if ok else "failed", "detail": detail})
        if not ok:
            blockers.append(f"{name}: {detail}")

    try:
        if args.task and not TASK_ID_RE.fullmatch(args.task):
            raise ContractError("invalid task id argument")
        if args.task_source == "manifest" and not args.task:
            raise ContractError("manifest mode requires an explicit task id")
        if args.task_source == "per-pr" and args.expected_head_repo.casefold() != args.repo_slug.casefold():
            raise ContractError("per-PR evidence requires a same-repository head")
        if args.task_source == "per-pr" and args.expected_base_ref.casefold() in {"main", "master"}:
            raise ContractError("per-PR evidence forbids stable base refs")
        if args.task_source == "per-pr" and (not args.trusted_repo or not args.expected_trusted_sha):
            raise ContractError("per-PR evidence requires a trusted checkout and its exact SHA")
        if not SHA_RE.fullmatch(args.expected_head_sha) or not SHA_RE.fullmatch(args.expected_base_sha):
            raise ContractError("head and base must be full lowercase commit SHAs")
        if args.task_source == "per-pr" and not SHA_RE.fullmatch(args.expected_trusted_sha):
            raise ContractError("trusted checkout must have a full lowercase commit SHA")

        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        base = _git(repo, "rev-parse", f"refs/remotes/origin/{args.expected_base_ref}").stdout.strip()
        record("exact_git_identity", head == args.expected_head_sha and base == args.expected_base_sha, f"head={head} base={base}")

        changed = _changed_files(repo, args.expected_base_ref)
        if args.task_source == "per-pr":
            if any(path.startswith(PER_PR_GOVERNED_PREFIXES) for path in changed):
                raise ContractError("per-PR evidence cannot change governed policy or workflow surfaces")
            task_id, task_relative = _per_pr_task(repo, args.expected_base_ref, changed)
            if args.task and args.task != task_id:
                raise ContractError("provided task id differs from selected per-PR task")
        else:
            manifest = _regular_text(repo, ".speculoos/manifest.yaml")
            manifest_task = _top_level_scalar(manifest, "current_task")
            task_id = args.task
            task_relative = f".speculoos/tasks/{task_id}.yaml"
        task = _regular_text(repo, task_relative)
        identity_ok = all(
            (
                args.task_source == "per-pr" or manifest_task == task_id,
                _top_level_scalar(task, "id") == task_id,
                _top_level_scalar(task, "branch") == args.expected_head_ref,
                _top_level_scalar(task, "base_branch") == args.expected_base_ref,
                _nested_scalar(task, "delivery_policy", "mode") == "inherit_branch_policy",
            )
        )
        record("task_identity", identity_ok, task_relative)

        packet = _regular_text(repo, f"specs/{task_id}/pr-body.md")
        commit_message = _regular_text(repo, f"specs/{task_id}/commit-message.txt")
        if args.task_source == "per-pr":
            required_packet_files = {
                task_relative,
                f"specs/{task_id}/pr-body.md",
                f"specs/{task_id}/commit-message.txt",
            }
            record("per_pr_packet_changed", required_packet_files.issubset(changed), task_id)
        packet_files = _packet_changed_files(packet)
        record("changed_files_match", packet_files == changed, f"packet={len(packet_files)} actual={len(changed)}")

        corpus = f"{packet}\n{commit_message}".casefold()
        release_ok = "feature prs target `dev`" in corpus and "release/promotion prs target `main`" in corpus
        record("release_policy_wording", release_ok, "canonical feature and promotion phrases")
        task_ok = task_id.casefold() in corpus
        record("task_reference", task_ok, task_id)

        docs_changed = [path for path in changed if path == "README.md" or path.startswith("docs/")]
        docs_section = _markdown_section(packet, "Documentation Impact")
        docs_refs = set(re.findall(r"`([^`\n]+)`", "\n".join(docs_section or [])))
        docs_ok = all(path in docs_refs for path in docs_changed)
        record("documentation_impact", docs_ok, f"changed_docs={len(docs_changed)}")

        trusted_repo = Path(args.trusted_repo).resolve() if args.task_source == "per-pr" else repo
        if args.task_source == "per-pr":
            if trusted_repo == repo:
                raise ContractError("per-PR workflow identity cannot trust the candidate checkout")
            trusted_head = _git(trusted_repo, "rev-parse", "HEAD").stdout.strip()
            record("exact_trusted_identity", trusted_head == args.expected_trusted_sha,
                   f"trusted_head={trusted_head}")
        manifest_json = json.loads(_regular_text(trusted_repo, "templates/repo-workflow-materialization-manifest.json"))
        workflow_name = "speculoos-trusted-canary.yml" if args.task_source == "per-pr" else "speculoos.yml"
        mapping = {
            "source": f"templates/starter-workflows/{workflow_name}",
            "target": f".github/workflows/{workflow_name}",
        }
        template = _regular_text(trusted_repo, mapping["source"])
        live = _regular_text(trusted_repo, mapping["target"])
        materialized_ok = mapping in (manifest_json.get("workflows") or []) and template == live
        record("workflow_materialization", materialized_ok, "canonical and live workflow identity")

        actor_ok, actor_detail = _actor_contract(repo)
        record("actor_policy", actor_ok, actor_detail)

        diff_check = _git(repo, "diff", "--check", f"origin/{args.expected_base_ref}...HEAD", check=False)
        record("diff_check", diff_check.returncode == 0, diff_check.stderr.strip() or "clean")

        added = _added_diff(repo, args.expected_base_ref)
        secret_hits = {name for name, pattern in SECRET_PATTERNS.items() if pattern.search(added)}
        blob_hits, unscannable = _scan_changed_text(repo, changed)
        secret_hits.update(blob_hits)
        scan_ok = not secret_hits and not unscannable
        detail = f"hits={','.join(sorted(secret_hits)) or 'none'} unscannable={len(unscannable)}"
        record("private_data_scan", scan_ok, detail)
    except (ContractError, UnicodeDecodeError, json.JSONDecodeError, OSError,
            subprocess.CalledProcessError) as exc:
        blockers.append(f"contract_error: {exc}")
        checks.append({"name": "contract_error", "status": "failed", "detail": str(exc)})

    return {
        "schema": "agent-toolkit-speculoos-pr-contract/v1",
        "status": "ok" if not blockers else "blocked",
        "repository": args.repo_slug,
        "task": task_id,
        "task_source": args.task_source,
        "head_ref": args.expected_head_ref,
        "head_sha": args.expected_head_sha,
        "base_ref": args.expected_base_ref,
        "base_sha": args.expected_base_sha,
        "checks": checks,
        "blockers": blockers,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--trusted-repo")
    parser.add_argument("--expected-trusted-sha", default="")
    parser.add_argument("--repo-slug", required=True)
    parser.add_argument("--expected-head-repo", default="")
    parser.add_argument("--task")
    parser.add_argument("--task-source", choices=("manifest", "per-pr"), default="manifest")
    parser.add_argument("--expected-head-ref", required=True)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--expected-base-ref", required=True)
    parser.add_argument("--expected-base-sha", required=True)
    parser.add_argument("--output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = validate(args)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    sys.stdout.write(encoded)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
