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


def _regular_text(repo: Path, relative: str) -> str:
    path = repo / relative
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"missing or unsafe file: {relative}")
    return path.read_text(encoding="utf-8")


def _top_level_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*([^#\n]*?)\s*$", text)
    if not match:
        raise ContractError(f"missing top-level field: {key}")
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if not value:
        raise ContractError(f"empty top-level field: {key}")
    return value


def _nested_scalar(text: str, section: str, key: str) -> str:
    section_match = re.search(
        rf"(?ms)^{re.escape(section)}:\s*\n(?P<body>(?:^[ \t]+.*(?:\n|\Z))*)",
        text,
    )
    if not section_match:
        raise ContractError(f"missing section: {section}")
    body = section_match.group("body")
    match = re.search(rf"(?m)^  {re.escape(key)}:\s*([^#\n]*?)\s*$", body)
    if not match:
        raise ContractError(f"missing field: {section}.{key}")
    value = match.group(1).strip().strip("'\"")
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
    output = _git(repo, "diff", "--name-only", "--diff-filter=ACMRD", f"origin/{base_ref}...HEAD").stdout
    return sorted({line for line in output.splitlines() if line})


def _added_diff(repo: Path, base_ref: str) -> str:
    output = _git(repo, "diff", "--no-ext-diff", "--no-color", "--unified=0", f"origin/{base_ref}...HEAD").stdout
    return "\n".join(
        line[1:]
        for line in output.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


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

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "status": "passed" if ok else "failed", "detail": detail})
        if not ok:
            blockers.append(f"{name}: {detail}")

    try:
        if not TASK_ID_RE.fullmatch(args.task):
            raise ContractError("invalid task id argument")
        if not SHA_RE.fullmatch(args.expected_head_sha) or not SHA_RE.fullmatch(args.expected_base_sha):
            raise ContractError("head and base must be full lowercase commit SHAs")

        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        base = _git(repo, "rev-parse", f"refs/remotes/origin/{args.expected_base_ref}").stdout.strip()
        record("exact_git_identity", head == args.expected_head_sha and base == args.expected_base_sha, f"head={head} base={base}")

        manifest = _regular_text(repo, ".speculoos/manifest.yaml")
        manifest_task = _top_level_scalar(manifest, "current_task")
        task_relative = f".speculoos/tasks/{args.task}.yaml"
        task = _regular_text(repo, task_relative)
        identity_ok = all(
            (
                manifest_task == args.task,
                _top_level_scalar(task, "id") == args.task,
                _top_level_scalar(task, "branch") == args.expected_head_ref,
                _top_level_scalar(task, "base_branch") == args.expected_base_ref,
                _nested_scalar(task, "delivery_policy", "mode") == "inherit_branch_policy",
            )
        )
        record("task_identity", identity_ok, task_relative)

        changed = _changed_files(repo, args.expected_base_ref)
        packet = _regular_text(repo, f"specs/{args.task}/pr-body.md")
        commit_message = _regular_text(repo, f"specs/{args.task}/commit-message.txt")
        packet_files = _packet_changed_files(packet)
        record("changed_files_match", packet_files == changed, f"packet={len(packet_files)} actual={len(changed)}")

        corpus = f"{packet}\n{commit_message}".casefold()
        release_ok = "feature prs target `dev`" in corpus and "release/promotion prs target `main`" in corpus
        record("release_policy_wording", release_ok, "canonical feature and promotion phrases")
        task_ok = args.task.casefold() in corpus
        record("task_reference", task_ok, args.task)

        docs_changed = [path for path in changed if path == "README.md" or path.startswith("docs/")]
        docs_section = _markdown_section(packet, "Documentation Impact")
        docs_ok = not docs_changed or (
            docs_section is not None and any(path in "\n".join(docs_section) for path in docs_changed)
        )
        record("documentation_impact", docs_ok, f"changed_docs={len(docs_changed)}")

        manifest_json = json.loads(_regular_text(repo, "templates/repo-workflow-materialization-manifest.json"))
        mapping = {
            "source": "templates/starter-workflows/speculoos.yml",
            "target": ".github/workflows/speculoos.yml",
        }
        template = _regular_text(repo, mapping["source"])
        live = _regular_text(repo, mapping["target"])
        materialized_ok = mapping in (manifest_json.get("workflows") or []) and template == live
        record("workflow_materialization", materialized_ok, "canonical and live workflow identity")

        actor_ok, actor_detail = _actor_contract(repo)
        record("actor_policy", actor_ok, actor_detail)

        diff_check = _git(repo, "diff", "--check", f"origin/{args.expected_base_ref}...HEAD", check=False)
        record("diff_check", diff_check.returncode == 0, diff_check.stderr.strip() or "clean")

        added = _added_diff(repo, args.expected_base_ref)
        secret_hits = [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(added)]
        record("private_data_scan", not secret_hits, ",".join(secret_hits) if secret_hits else "no red-list token patterns")
    except (ContractError, json.JSONDecodeError, OSError, subprocess.CalledProcessError) as exc:
        blockers.append(f"contract_error: {exc}")
        checks.append({"name": "contract_error", "status": "failed", "detail": str(exc)})

    return {
        "schema": "agent-toolkit-speculoos-pr-contract/v1",
        "status": "ok" if not blockers else "blocked",
        "repository": args.repo_slug,
        "task": args.task,
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
    parser.add_argument("--repo-slug", required=True)
    parser.add_argument("--task", required=True)
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
