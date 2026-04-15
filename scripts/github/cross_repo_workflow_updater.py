#!/usr/bin/env python3
"""
cross_repo_workflow_updater.py

Safe V1 updater for cross-repo starter-workflow distribution.

Current behavior:
- loads and validates the cross-repo distribution manifest
- determines changed starter templates from git diff or manual filters
- resolves impacted consumer bindings
- resolves target branches from manifest or local consumer clones when available
- performs a safe divergence check by comparing consumer workflow files against
  current and historical revisions of the registered shared starter template
- can preview or apply exact-managed workflow updates in local consumer clones
- can push an updater branch and create a pull request through an automatic provider chain
- writes a machine-readable summary artifact

Current local runtime requirements:
- git
- python3
- at least one PR provider/auth path: `gh`, or a GitHub token discoverable via env / `gh auth token` / `.netrc`, or embedded HTTPS remote credentials
"""

from __future__ import annotations

import argparse
import difflib
import json
import netrc
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_BINDING_PREFIX = "templates/starter-workflows/"
ALLOWED_TARGET_PREFIX = ".github/workflows/"
GITHUB_TOKEN_ENV_NAMES = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITHUB_PAT",
    "GITHUB_API_TOKEN",
    "GITHUB_OAUTH_TOKEN",
    "GITHUB_APP_TOKEN",
)
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
USES_SHA_RE = re.compile(r"^\s*uses:\s*[^\s#]+@([a-f0-9]{40})\s*$", re.MULTILINE)
SHARED_REF_RE = re.compile(r"^\s*shared_repository_ref:\s*([a-f0-9]{40})\s*$", re.MULTILINE)


@dataclass
class BindingPreview:
    starter_template: str
    target_path: str
    status: str
    message: str
    matched_template_commit: str | None = None
    current_pinned_refs: list[str] | None = None
    candidate_pinned_refs: list[str] | None = None


@dataclass
class ConsumerPreview:
    repo: str
    resolved_base_branch: str | None
    status: str
    message: str
    bindings: list[BindingPreview]
    local_repo_path: str | None = None
    updater_branch: str | None = None
    pull_request_url: str | None = None
    pull_request_provider: str | None = None
    commit_sha: str | None = None
    review_report_path: str | None = None
    normalization_patch_path: str | None = None


@dataclass
class GitHubRemote:
    host: str
    owner: str
    repo: str
    api_base: str
    graphql_url: str
    embedded_token: str | None = None


class StarterTemplateHistory:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._commits_cache: dict[str, list[str]] = {}
        self._text_cache: dict[tuple[str, str], str] = {}

    def commits_for_path(self, rel_path: str) -> list[str]:
        rel_path = rel_path.strip()
        if rel_path not in self._commits_cache:
            out = run_git(self.repo_root, ["log", "--format=%H", "--", rel_path])
            commits = [line.strip() for line in out.splitlines() if line.strip()]
            self._commits_cache[rel_path] = commits
        return self._commits_cache[rel_path]

    def read_text_at_commit(self, commit: str, rel_path: str) -> str:
        key = (commit, rel_path)
        if key not in self._text_cache:
            text = run_git(self.repo_root, ["show", f"{commit}:{rel_path}"])
            self._text_cache[key] = text
        return self._text_cache[key]

    def find_matching_commit(self, rel_path: str, candidate_text: str) -> str | None:
        for commit in self.commits_for_path(rel_path):
            if self.read_text_at_commit(commit, rel_path) == candidate_text:
                return commit
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--manifest-path", required=True, type=Path)
    parser.add_argument("--source-commit", required=True, type=str)
    parser.add_argument("--previous-source-commit", default="", type=str)
    parser.add_argument("--consumer-local-root", type=Path, help="Optional directory containing local consumer clones by repo name")
    parser.add_argument("--consumer-filter", action="append", default=[])
    parser.add_argument("--starter-template-filter", action="append", default=[])
    parser.add_argument("--out-summary", default="artifacts/cross-repo-workflow-updater-summary.json", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Apply updates into local consumer clones and create local commits")
    parser.add_argument(
        "--create-pr",
        action="store_true",
        help="Push updater branches and open pull requests using the automatic provider chain (gh, REST API, GraphQL API)",
    )
    parser.add_argument(
        "--manual-review-on-divergence",
        action="store_true",
        help="When divergence blocks a normal sync PR, create a manual-review PR/report path instead of stopping at manual_review_required.",
    )
    parser.add_argument(
        "--manual-review-artifact-dir",
        default="docs/shared-workflow-reviews",
        help="Directory inside the consumer repo where manual-review artifacts should be written.",
    )
    parser.add_argument(
        "--include-normalization-patch",
        action="store_true",
        help="When creating manual-review artifacts, also write an optional proposed normalization patch.",
    )
    parser.add_argument("--branch-prefix", default="chore/sync-shared-workflows-")
    return parser.parse_args()


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"JSON file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to parse JSON file {path}: {exc}")


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    data = load_json(manifest_path)
    if str(data.get("schemaVersion") or "").strip() != "1.0.0":
        raise SystemExit("Unsupported or missing manifest schemaVersion. Expected 1.0.0")

    consumers = data.get("consumers")
    if not isinstance(consumers, list):
        raise SystemExit("Manifest key 'consumers' must be a list.")

    for consumer in consumers:
        if not isinstance(consumer, dict):
            raise SystemExit("Each consumer entry must be an object.")
        repo = str(consumer.get("repo") or "").strip()
        if not repo or "/" not in repo:
            raise SystemExit(f"Consumer entry has invalid repo slug: {repo!r}")
        base_branch = consumer.get("baseBranch")
        if base_branch is not None and not str(base_branch).strip():
            raise SystemExit(f"Consumer {repo} has an empty baseBranch value.")

        bindings = consumer.get("managedBindings")
        if not isinstance(bindings, list):
            raise SystemExit(f"Consumer {repo} must define managedBindings as a list.")

        for binding in bindings:
            if not isinstance(binding, dict):
                raise SystemExit(f"Consumer {repo} has a non-object binding entry.")
            starter_template = normalize_path(str(binding.get("starterTemplate") or "").strip())
            target_path = normalize_path(str(binding.get("targetPath") or "").strip())
            divergence_policy = str(binding.get("divergencePolicy") or "").strip()
            if not starter_template.startswith(ALLOWED_BINDING_PREFIX):
                raise SystemExit(
                    f"Consumer {repo} binding starterTemplate must live under {ALLOWED_BINDING_PREFIX}: {starter_template}"
                )
            if not target_path.startswith(ALLOWED_TARGET_PREFIX):
                raise SystemExit(
                    f"Consumer {repo} binding targetPath must live under {ALLOWED_TARGET_PREFIX}: {target_path}"
                )
            if divergence_policy != "exact":
                raise SystemExit(
                    f"Consumer {repo} binding {target_path} must use divergencePolicy='exact' in V1."
                )
            binding["starterTemplate"] = starter_template
            binding["targetPath"] = target_path
    return data


def run_command(cmd: list[str], cwd: Path, check: bool = True) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Command failed ({' '.join(cmd)}): {stderr}")
    return (completed.stdout or "").strip()


def run_git(repo_root: Path, args: list[str], check: bool = True) -> str:
    try:
        return run_command(["git", *args], cwd=repo_root, check=check)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def extract_pinned_refs(text: str) -> list[str]:
    refs = USES_SHA_RE.findall(text) + SHARED_REF_RE.findall(text)
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return deduped


def resolve_changed_starter_templates(
    repo_root: Path,
    previous_source_commit: str,
    source_commit: str,
    manual_filters: list[str],
) -> list[str]:
    if manual_filters:
        return sorted({normalize_path(item.strip()) for item in manual_filters if item.strip()})

    zero = "0" * 40
    if not previous_source_commit or previous_source_commit == zero:
        changed = set()
        for suffix in ("*.yml", "*.yaml"):
            for path in repo_root.glob(f"templates/starter-workflows/{suffix}"):
                changed.add(normalize_path(str(path.relative_to(repo_root))))
        return sorted(changed)

    out = run_git(
        repo_root,
        [
            "diff",
            "--name-only",
            f"{previous_source_commit}...{source_commit}",
            "--",
            "templates/starter-workflows/*.yml",
            "templates/starter-workflows/*.yaml",
        ],
    )
    return sorted(normalize_path(line.strip()) for line in out.splitlines() if line.strip())


def repo_name_from_slug(repo_slug: str) -> str:
    return repo_slug.split("/", 1)[1]


def resolve_consumer_local_repo(consumer_local_root: Path | None, repo_slug: str) -> Path | None:
    if consumer_local_root is None:
        return None
    candidate = consumer_local_root / repo_name_from_slug(repo_slug)
    if (candidate / ".git").exists():
        return candidate.resolve()
    return None


def resolve_default_branch(local_repo: Path) -> str | None:
    completed = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=local_repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        ref = (completed.stdout or "").strip()
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix):
            return ref[len(prefix):]

    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=local_repo,
        text=True,
        capture_output=True,
        check=False,
    )
    branch = (completed.stdout or "").strip()
    return branch or None


def read_text_if_exists(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def classify_binding_preview(
    repo_root: Path,
    consumer_repo: Path,
    binding: dict[str, Any],
    history: StarterTemplateHistory,
) -> BindingPreview:
    starter_template = str(binding["starterTemplate"])
    target_path = str(binding["targetPath"])

    source_path = repo_root / starter_template
    if not source_path.exists():
        return BindingPreview(
            starter_template=starter_template,
            target_path=target_path,
            status="render_failed",
            message=f"Starter template not found: {starter_template}",
        )

    source_text = source_path.read_text(encoding="utf-8")
    candidate_pinned_refs = extract_pinned_refs(source_text)
    consumer_target = consumer_repo / target_path
    target_text = read_text_if_exists(consumer_target)

    if target_text is None:
        return BindingPreview(
            starter_template=starter_template,
            target_path=target_path,
            status="candidate_create",
            message="Target workflow file is missing and would be created.",
            candidate_pinned_refs=candidate_pinned_refs,
        )

    current_pinned_refs = extract_pinned_refs(target_text)
    if target_text == source_text:
        return BindingPreview(
            starter_template=starter_template,
            target_path=target_path,
            status="no_change",
            message="Consumer target already matches the canonical starter template.",
            current_pinned_refs=current_pinned_refs,
            candidate_pinned_refs=candidate_pinned_refs,
        )

    matched_commit = history.find_matching_commit(starter_template, target_text)
    if matched_commit:
        return BindingPreview(
            starter_template=starter_template,
            target_path=target_path,
            status="candidate_update",
            message=(
                "Consumer target matches a prior canonical starter-template revision and can be updated safely. "
                f"matched_template_commit={matched_commit}"
            ),
            matched_template_commit=matched_commit,
            current_pinned_refs=current_pinned_refs,
            candidate_pinned_refs=candidate_pinned_refs,
        )

    return BindingPreview(
        starter_template=starter_template,
        target_path=target_path,
        status="diverged",
        message=(
            "Consumer target does not match the current or any historical revision of the registered starter template. "
            "Manual review is required before overwriting this exact-managed binding."
        ),
        current_pinned_refs=current_pinned_refs,
        candidate_pinned_refs=candidate_pinned_refs,
    )


def git_worktree_is_clean(repo_root: Path) -> bool:
    out = run_command(["git", "status", "--porcelain"], cwd=repo_root, check=False)
    return not out.strip()


def validate_yaml_if_possible(path: Path) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception:
        return True, "PyYAML unavailable, skipped YAML parse validation."

    try:
        yaml.safe_load(text)
        return True, "YAML parsed successfully."
    except Exception as exc:
        return False, f"YAML parse failed: {exc}"


def prepare_updater_branch(local_repo: Path, base_branch: str, updater_branch: str) -> None:
    if not git_worktree_is_clean(local_repo):
        raise RuntimeError("Consumer repo working tree is not clean.")
    run_command(["git", "fetch", "origin", base_branch], cwd=local_repo)
    run_command(["git", "checkout", "-B", updater_branch, f"origin/{base_branch}"], cwd=local_repo)
    if not git_worktree_is_clean(local_repo):
        raise RuntimeError("Consumer repo working tree became dirty immediately after branch preparation.")


def apply_managed_updates(repo_root: Path, local_repo: Path, bindings: list[BindingPreview]) -> list[str]:
    changed_paths: list[str] = []
    for binding in bindings:
        if binding.status not in {"candidate_create", "candidate_update"}:
            continue
        source_path = repo_root / binding.starter_template
        target_path = local_repo / binding.target_path
        source_text = source_path.read_text(encoding="utf-8")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(source_text, encoding="utf-8")
        run_command(["git", "add", binding.target_path], cwd=local_repo)
        changed_paths.append(binding.target_path)
    return changed_paths


def validate_staged_targets(local_repo: Path, changed_paths: list[str]) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    for rel_path in changed_paths:
        full_path = local_repo / rel_path
        valid, message = validate_yaml_if_possible(full_path)
        messages.append(f"{rel_path}: {message}")
        if not valid:
            ok = False
    return ok, messages


def collect_binding_diff_facts(repo_root: Path, local_repo: Path, binding: BindingPreview) -> list[str]:
    source_text = (repo_root / binding.starter_template).read_text(encoding="utf-8")
    target_text = (local_repo / binding.target_path).read_text(encoding="utf-8")
    facts: list[str] = []

    if binding.current_pinned_refs or binding.candidate_pinned_refs:
        facts.append(
            f"Pinned reusable-workflow refs differ: current={binding.current_pinned_refs or []}, candidate={binding.candidate_pinned_refs or []}."
        )

    if "WORKFLOW_PUSH_TOKEN" in source_text and "WORKFLOW_PUSH_TOKEN" not in target_text:
        facts.append("Consumer file does not pass through `WORKFLOW_PUSH_TOKEN`, while the shared starter template does.")
    if "auto_commit: true" in target_text and "auto_commit: true" not in source_text:
        facts.append("Consumer file currently forces `auto_commit: true`, while the shared starter template defers to vars/default false.")
    if "auto_push: true" in target_text and "auto_push: true" not in source_text:
        facts.append("Consumer file currently forces `auto_push: true`, while the shared starter template defers to vars/default false.")

    source_shared_lines = [line.strip() for line in source_text.splitlines() if "shared_repository_ref:" in line]
    target_shared_lines = [line.strip() for line in target_text.splitlines() if "shared_repository_ref:" in line]
    if source_shared_lines != target_shared_lines:
        facts.append(
            f"`shared_repository_ref` handling differs: current={target_shared_lines or ['<absent>']}, candidate={source_shared_lines or ['<absent>']}."
        )

    source_input_lines = [line.strip() for line in source_text.splitlines() if line.strip().startswith("shared_repository_ref:")]
    target_input_lines = [line.strip() for line in target_text.splitlines() if line.strip().startswith("shared_repository_ref:")]
    if source_input_lines != target_input_lines and any("workflow_dispatch" in text for text in [source_text, target_text]):
        facts.append("The input contract around `shared_repository_ref` differs between the consumer workflow and the shared starter template.")

    if not facts:
        facts.append("The consumer file differs from the shared starter template, but no specific high-level contract fact was extracted automatically.")
    return facts


def build_normalization_patch_text(repo_root: Path, local_repo: Path, bindings: list[BindingPreview]) -> str:
    parts: list[str] = []
    for binding in bindings:
        current_text = (local_repo / binding.target_path).read_text(encoding="utf-8").splitlines(keepends=True)
        desired_text = (repo_root / binding.starter_template).read_text(encoding="utf-8").splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                current_text,
                desired_text,
                fromfile=f"a/{binding.target_path}",
                tofile=f"b/{binding.target_path}",
                lineterm="",
            )
        )
        if diff_lines:
            parts.append("\n".join(diff_lines) + "\n")
    return "\n".join(parts)


def build_manual_review_report(
    repo_root: Path,
    local_repo: Path,
    shared_repository: str,
    source_commit: str,
    consumer: ConsumerPreview,
    diverged_bindings: list[BindingPreview],
) -> str:
    lines = [
        f"# Shared workflow divergence review for `{consumer.repo}`",
        "",
        f"Shared source: `{shared_repository}` at `{source_commit}`",
        f"Target branch: `{consumer.resolved_base_branch}`",
        "",
        "## 1. Scope",
        "",
        "Compared these registered shared starter templates against the current consumer workflow files:",
        "",
    ]
    for binding in diverged_bindings:
        lines.append(f"- `{binding.starter_template}` -> `{binding.target_path}`")

    lines.extend(["", "## 2. Verified diff facts", ""])
    for binding in diverged_bindings:
        lines.append(f"### `{binding.target_path}`")
        for fact in collect_binding_diff_facts(repo_root, local_repo, binding):
            lines.append(f"- {fact}")
        lines.append("")

    lines.extend(
        [
            "## 3. Interpretation",
            "",
            "The updater blocked a normal sync PR because these files do not exactly match the current or registered historical starter-template path lineage.",
            "That does not prove the consumer is wrong. It means this case needs adjudication before an exact-managed overwrite is allowed.",
            "",
            "## 4. Confidence and doubts",
            "",
            "- Confidence: moderate, based on deterministic file comparison and contract-level fact extraction.",
            "- Doubt: the remaining differences may reflect either older managed lineage outside the current exact path history, or an intentional consumer-specific operational choice.",
            "",
            "## 5. Recommendation",
            "",
            "Recommendation: adjudicate manually before any normalization PR is merged.",
            "",
            "Questions to answer in review:",
            "- Should this consumer remain on the older dynamic `shared_repository_ref` behavior, or be normalized to the current pinned shared-template model?",
            "- Should `WORKFLOW_PUSH_TOKEN` passthrough be adopted here, or intentionally remain absent?",
            "- Should this consumer continue forcing `auto_commit` / `auto_push`, or should it inherit the newer shared starter-template defaults?",
            "",
            "Any proposed normalization patch in this PR is optional and should be treated as review material, not as an automatically approved overwrite.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_manual_review_artifacts(
    repo_root: Path,
    local_repo: Path,
    consumer: ConsumerPreview,
    diverged_bindings: list[BindingPreview],
    shared_repository: str,
    source_commit: str,
    artifact_dir: str,
    include_normalization_patch: bool,
) -> tuple[list[str], str, str | None]:
    repo_name = repo_name_from_slug(consumer.repo)
    base_dir = local_repo / artifact_dir
    base_dir.mkdir(parents=True, exist_ok=True)

    report_rel = normalize_path(f"{artifact_dir.rstrip('/')}/{repo_name}-shared-workflow-divergence-{source_commit[:7]}.md")
    report_path = local_repo / report_rel
    report_text = build_manual_review_report(repo_root, local_repo, shared_repository, source_commit, consumer, diverged_bindings)
    report_path.write_text(report_text, encoding="utf-8")

    changed_paths = [report_rel]
    patch_rel: str | None = None
    if include_normalization_patch:
        patch_rel = normalize_path(f"{artifact_dir.rstrip('/')}/{repo_name}-shared-workflow-normalization-{source_commit[:7]}.patch")
        patch_path = local_repo / patch_rel
        patch_text = build_normalization_patch_text(repo_root, local_repo, diverged_bindings)
        patch_path.write_text(patch_text, encoding="utf-8")
        changed_paths.append(patch_rel)

    for rel_path in changed_paths:
        run_command(["git", "add", rel_path], cwd=local_repo)
    return changed_paths, report_rel, patch_rel


def build_pr_title(shared_repository: str, source_commit: str) -> str:
    return f"chore(ci): sync shared workflows from {shared_repository}@{source_commit[:7]}"


def build_commit_message(shared_repository: str, source_commit: str) -> str:
    return build_pr_title(shared_repository, source_commit)


def build_pr_body(
    shared_repository: str,
    source_commit: str,
    consumer: ConsumerPreview,
    validation_messages: list[str],
) -> str:
    lines = [
        f"Sync shared workflows from `{shared_repository}` at `{source_commit}`.",
        "",
        f"Target branch: `{consumer.resolved_base_branch}`",
        "",
        "Updated bindings:",
    ]
    for binding in consumer.bindings:
        if binding.status not in {"candidate_create", "candidate_update"}:
            continue
        lines.append(f"- `{binding.starter_template}` -> `{binding.target_path}`")
        if binding.matched_template_commit:
            lines.append(f"  - previous managed template revision: `{binding.matched_template_commit}`")
        if binding.current_pinned_refs or binding.candidate_pinned_refs:
            lines.append(
                f"  - pinned refs: before={binding.current_pinned_refs or []} after={binding.candidate_pinned_refs or []}"
            )
    lines.extend(["", "Validation:"])
    lines.extend(f"- {message}" for message in validation_messages)
    lines.extend(["", "If this causes trouble, this PR is safe to revert."])
    return "\n".join(lines) + "\n"


def build_manual_review_title(shared_repository: str, source_commit: str) -> str:
    return f"docs(ci): review shared workflow divergence from {shared_repository}@{source_commit[:7]}"


def build_manual_review_body(
    shared_repository: str,
    source_commit: str,
    consumer: ConsumerPreview,
) -> str:
    lines = [
        f"This PR does **not** normalize the managed workflow files yet.",
        "",
        f"It captures a manual-review report for divergence detected while checking `{consumer.repo}` against shared starter templates from `{shared_repository}` at `{source_commit}`.",
        "",
        f"Target branch: `{consumer.resolved_base_branch}`",
        f"Review report: `{consumer.review_report_path}`" if consumer.review_report_path else "Review report: `<not generated>`",
    ]
    if consumer.normalization_patch_path:
        lines.append(f"Optional proposed normalization patch: `{consumer.normalization_patch_path}`")

    lines.extend(
        [
            "",
            "Artifact lifecycle for this PR:",
            "- These files are review scaffolding only. They are meant to support adjudication, not to become permanent runtime assets by default.",
            "- This PR should normally stay discussion-only until the reviewer decides whether to normalize the workflows or treat this repo as intentionally customized.",
            "- If normalization is approved, the preferred next step is a clean follow-up PR that changes the live `.github/workflows/` files directly, without keeping these review artifacts as long-term repo content unless there is a specific reason to archive them.",
            "- If customization is intentional, the preferred next step is to close this PR and relax or remove exact-managed treatment for these bindings rather than merging artifact-only files into the long-term branch by accident.",
            "",
            "Review focus:",
            "- Were the current consumer workflows intentionally kept on the older `shared_repository_ref` behavior?",
            "- Should `WORKFLOW_PUSH_TOKEN` passthrough be adopted here?",
            "- Should the repo keep forcing `auto_commit` / `auto_push`, or move to the newer shared-template defaults?",
            "- Should this consumer stay in exact-managed scope, or be treated as intentionally customized?",
            "",
            "This PR is for adjudication first. Any normalization patch included here is optional review material.",
        ]
    )
    return "\n".join(lines) + "\n"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def resolve_github_remote(local_repo: Path) -> GitHubRemote | None:
    remote_url = run_command(["git", "remote", "get-url", "origin"], cwd=local_repo, check=False).strip()
    if not remote_url:
        return None

    host: str | None = None
    owner: str | None = None
    repo: str | None = None
    embedded_token: str | None = None

    parsed = urllib.parse.urlparse(remote_url)
    if parsed.scheme in {"http", "https", "ssh"} and parsed.hostname:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            host = parsed.hostname
            owner = parts[0]
            repo = parts[1]
            if parsed.password:
                embedded_token = parsed.password
    else:
        match = re.match(r"^git@([^:]+):([^/]+)/([^/]+?)(?:\.git)?$", remote_url)
        if match:
            host, owner, repo = match.groups()

    if not host or not owner or not repo:
        return None

    if repo.endswith(".git"):
        repo = repo[:-4]
    if host == "github.com":
        api_base = "https://api.github.com"
        graphql_url = "https://api.github.com/graphql"
    else:
        api_base = f"https://{host}/api/v3"
        graphql_url = f"https://{host}/api/graphql"
    return GitHubRemote(
        host=host,
        owner=owner,
        repo=repo,
        api_base=api_base,
        graphql_url=graphql_url,
        embedded_token=embedded_token,
    )


def discover_github_token(remote: GitHubRemote | None, local_repo: Path) -> tuple[str | None, str | None]:
    for env_name in GITHUB_TOKEN_ENV_NAMES:
        value = (os.environ.get(env_name) or "").strip()
        if value:
            return value, f"env:{env_name}"

    if remote and remote.embedded_token:
        return remote.embedded_token, "git-remote-embedded"

    if command_exists("gh"):
        cmd = ["gh", "auth", "token"]
        if remote and remote.host:
            cmd.extend(["--hostname", remote.host])
        completed = subprocess.run(cmd, cwd=local_repo, text=True, capture_output=True, check=False)
        token = (completed.stdout or "").strip()
        if completed.returncode == 0 and token:
            return token, "gh-auth-token"

    if remote:
        hosts_to_try = [remote.host]
        if remote.host == "github.com":
            hosts_to_try.append("api.github.com")
        try:
            auths = netrc.netrc()
            for host in hosts_to_try:
                creds = auths.authenticators(host)
                if creds and creds[2]:
                    return creds[2], f"netrc:{host}"
        except (FileNotFoundError, netrc.NetrcParseError):
            pass

    return None, None


def github_json_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "cross-repo-workflow-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(body) if body else None
        except Exception:
            error_payload = body
        detail = error_payload.get("message") if isinstance(error_payload, dict) else str(error_payload)
        if isinstance(error_payload, dict) and error_payload.get("errors"):
            detail = f"{detail}; errors={error_payload['errors']}"
        raise RuntimeError(f"GitHub API request failed ({method} {url}): {detail}") from exc
    if not body:
        return None
    try:
        return json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"GitHub API returned non-JSON response for {method} {url}") from exc


def github_graphql_request(endpoint: str, token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    payload = github_json_request("POST", endpoint, token, {"query": query, "variables": variables})
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub GraphQL response was not a JSON object.")
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL request failed: {payload['errors']}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("GitHub GraphQL response did not include a data object.")
    return data


def detect_existing_pr_with_gh(local_repo: Path, updater_branch: str) -> str | None:
    completed = subprocess.run(
        ["gh", "pr", "list", "--head", updater_branch, "--state", "open", "--json", "url"],
        cwd=local_repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(stderr or "gh pr list failed")
    try:
        data = json.loads(completed.stdout or "[]")
    except Exception as exc:
        raise RuntimeError("gh pr list returned invalid JSON") from exc
    if isinstance(data, list) and data:
        url = data[0].get("url")
        return str(url) if url else None
    return None


def detect_existing_pr_with_rest(local_repo: Path, remote: GitHubRemote, updater_branch: str, token: str) -> str | None:
    query = urllib.parse.urlencode({"head": f"{remote.owner}:{updater_branch}", "state": "open", "per_page": 1})
    payload = github_json_request("GET", f"{remote.api_base}/repos/{remote.owner}/{remote.repo}/pulls?{query}", token)
    if isinstance(payload, list) and payload:
        url = payload[0].get("html_url") or payload[0].get("url")
        return str(url) if url else None
    return None


def detect_existing_pr_with_graphql(remote: GitHubRemote, updater_branch: str, token: str) -> str | None:
    data = github_graphql_request(
        remote.graphql_url,
        token,
        """
        query($owner: String!, $name: String!, $branch: String!) {
          repository(owner: $owner, name: $name) {
            pullRequests(states: OPEN, headRefName: $branch, first: 1) {
              nodes {
                url
              }
            }
          }
        }
        """,
        {"owner": remote.owner, "name": remote.repo, "branch": updater_branch},
    )
    repository = data.get("repository") or {}
    pull_requests = repository.get("pullRequests") or {}
    nodes = pull_requests.get("nodes") or []
    if nodes:
        url = nodes[0].get("url")
        return str(url) if url else None
    return None


def detect_existing_pr(local_repo: Path, updater_branch: str, remote: GitHubRemote | None, token: str | None) -> tuple[str | None, str | None, list[str]]:
    errors: list[str] = []

    if command_exists("gh"):
        try:
            url = detect_existing_pr_with_gh(local_repo, updater_branch)
            if url:
                return url, "gh", errors
        except RuntimeError as exc:
            errors.append(f"gh detect existing PR failed: {exc}")

    if remote and token:
        try:
            url = detect_existing_pr_with_rest(local_repo, remote, updater_branch, token)
            if url:
                return url, "rest", errors
        except RuntimeError as exc:
            errors.append(f"rest detect existing PR failed: {exc}")

        try:
            url = detect_existing_pr_with_graphql(remote, updater_branch, token)
            if url:
                return url, "graphql", errors
        except RuntimeError as exc:
            errors.append(f"graphql detect existing PR failed: {exc}")

    return None, None, errors


def create_pull_request_with_gh(local_repo: Path, base_branch: str, updater_branch: str, title: str, body: str) -> str:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(body)
        body_path = handle.name
    try:
        url = run_command(
            ["gh", "pr", "create", "--base", base_branch, "--head", updater_branch, "--title", title, "--body-file", body_path],
            cwd=local_repo,
        )
        return url.strip()
    finally:
        Path(body_path).unlink(missing_ok=True)


def create_pull_request_with_rest(
    local_repo: Path,
    remote: GitHubRemote,
    base_branch: str,
    updater_branch: str,
    title: str,
    body: str,
    token: str,
) -> str:
    existing = detect_existing_pr_with_rest(local_repo, remote, updater_branch, token)
    if existing:
        return existing
    payload = github_json_request(
        "POST",
        f"{remote.api_base}/repos/{remote.owner}/{remote.repo}/pulls",
        token,
        {
            "title": title,
            "head": updater_branch,
            "base": base_branch,
            "body": body,
        },
    )
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub REST PR creation returned a non-object response.")
    url = payload.get("html_url") or payload.get("url")
    if not url:
        raise RuntimeError("GitHub REST PR creation did not return a PR URL.")
    return str(url)


def create_pull_request_with_graphql(
    remote: GitHubRemote,
    base_branch: str,
    updater_branch: str,
    title: str,
    body: str,
    token: str,
) -> str:
    existing = detect_existing_pr_with_graphql(remote, updater_branch, token)
    if existing:
        return existing
    repository_data = github_graphql_request(
        remote.graphql_url,
        token,
        """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            id
          }
        }
        """,
        {"owner": remote.owner, "name": remote.repo},
    )
    repository = repository_data.get("repository") or {}
    repository_id = repository.get("id")
    if not repository_id:
        raise RuntimeError("GitHub GraphQL repository lookup did not return an id.")
    mutation_data = github_graphql_request(
        remote.graphql_url,
        token,
        """
        mutation(
          $repositoryId: ID!,
          $baseRefName: String!,
          $headRefName: String!,
          $title: String!,
          $body: String!
        ) {
          createPullRequest(
            input: {
              repositoryId: $repositoryId,
              baseRefName: $baseRefName,
              headRefName: $headRefName,
              title: $title,
              body: $body
            }
          ) {
            pullRequest {
              url
            }
          }
        }
        """,
        {
            "repositoryId": repository_id,
            "baseRefName": base_branch,
            "headRefName": updater_branch,
            "title": title,
            "body": body,
        },
    )
    create_pr = (mutation_data.get("createPullRequest") or {}).get("pullRequest") or {}
    url = create_pr.get("url")
    if not url:
        raise RuntimeError("GitHub GraphQL PR creation did not return a PR URL.")
    return str(url)


def create_pull_request(local_repo: Path, base_branch: str, updater_branch: str, title: str, body: str) -> tuple[str, str]:
    run_command(["git", "push", "--force-with-lease", "--set-upstream", "origin", updater_branch], cwd=local_repo)
    remote = resolve_github_remote(local_repo)
    token, token_source = discover_github_token(remote, local_repo)
    existing, existing_provider, detect_errors = detect_existing_pr(local_repo, updater_branch, remote, token)
    if existing:
        suffix = f"+{token_source}" if existing_provider in {"rest", "graphql"} and token_source else ""
        return existing, f"{existing_provider}{suffix}"

    errors = list(detect_errors)

    if command_exists("gh"):
        try:
            return create_pull_request_with_gh(local_repo, base_branch, updater_branch, title, body), "gh"
        except RuntimeError as exc:
            errors.append(f"gh create PR failed: {exc}")
    else:
        errors.append("gh create PR skipped: gh not installed")

    if remote and token:
        try:
            return create_pull_request_with_rest(local_repo, remote, base_branch, updater_branch, title, body, token), f"rest+{token_source}"
        except RuntimeError as exc:
            errors.append(f"rest create PR failed: {exc}")

        try:
            return create_pull_request_with_graphql(remote, base_branch, updater_branch, title, body, token), f"graphql+{token_source}"
        except RuntimeError as exc:
            errors.append(f"graphql create PR failed: {exc}")
    else:
        if not remote:
            errors.append("API create PR skipped: could not resolve GitHub origin remote")
        if not token:
            errors.append(
                "API create PR skipped: no GitHub token found via env, embedded remote credentials, gh auth token, or netrc"
            )

    raise RuntimeError("Failed to open pull request automatically. Tried providers: " + " | ".join(errors))


def evaluate_consumer(
    repo_root: Path,
    consumer: dict[str, Any],
    changed_templates: set[str],
    consumer_local_root: Path | None,
    history: StarterTemplateHistory,
    source_commit: str,
    shared_repository: str,
    dry_run: bool,
    execute: bool,
    create_pr: bool,
    manual_review_on_divergence: bool,
    manual_review_artifact_dir: str,
    include_normalization_patch: bool,
    branch_prefix: str,
) -> ConsumerPreview:
    repo_slug = str(consumer["repo"])
    impacted_bindings_raw = [
        binding
        for binding in consumer.get("managedBindings", [])
        if binding.get("enabled", True) and str(binding.get("starterTemplate")) in changed_templates
    ]

    if not impacted_bindings_raw:
        return ConsumerPreview(
            repo=repo_slug,
            resolved_base_branch=None,
            status="not_impacted",
            message="No enabled managed bindings were impacted by the changed starter templates.",
            bindings=[],
        )

    local_repo = resolve_consumer_local_repo(consumer_local_root, repo_slug)
    base_branch = str(consumer.get("baseBranch") or "").strip() or None
    if base_branch is None:
        if local_repo is None:
            return ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=None,
                status="branch_resolution_failed",
                message="baseBranch is omitted and no local consumer clone was available to resolve the default branch.",
                bindings=[],
            )
        base_branch = resolve_default_branch(local_repo)
        if not base_branch:
            return ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=None,
                status="branch_resolution_failed",
                message="Failed to resolve the consumer repository default branch from the local clone.",
                bindings=[],
            )

    if local_repo is None:
        bindings = [
            BindingPreview(
                starter_template=str(binding["starterTemplate"]),
                target_path=str(binding["targetPath"]),
                status="consumer_repo_unavailable",
                message="No local consumer clone was available, so content preview could not run.",
            )
            for binding in impacted_bindings_raw
        ]
        return ConsumerPreview(
            repo=repo_slug,
            resolved_base_branch=base_branch,
            status="preview_incomplete",
            message="Impacted bindings were found, but no local consumer clone was available for content preview.",
            bindings=bindings,
        )

    previews = [classify_binding_preview(repo_root, local_repo, binding, history) for binding in impacted_bindings_raw]
    candidate_bindings = [item for item in previews if item.status in {"candidate_create", "candidate_update"}]
    diverged_bindings = [item for item in previews if item.status == "diverged"]
    updater_branch = f"{branch_prefix}{source_commit[:7]}"

    if diverged_bindings:
        base_preview = ConsumerPreview(
            repo=repo_slug,
            resolved_base_branch=base_branch,
            status="manual_review_required",
            message=(
                f"Found {len(diverged_bindings)} diverged exact-managed binding(s). "
                "No normal update PR will be created until the divergence is reviewed."
            ),
            bindings=previews,
            local_repo_path=str(local_repo),
            updater_branch=updater_branch,
        )
        if not manual_review_on_divergence:
            return base_preview
        if dry_run or not execute:
            base_preview.status = "would_open_manual_review_pr"
            base_preview.message = (
                f"Found {len(diverged_bindings)} diverged exact-managed binding(s). "
                "A manual-review PR would be opened instead of a normal sync PR."
            )
            return base_preview
        try:
            prepare_updater_branch(local_repo, base_branch, updater_branch)
            changed_paths, report_rel, patch_rel = write_manual_review_artifacts(
                repo_root=repo_root,
                local_repo=local_repo,
                consumer=base_preview,
                diverged_bindings=diverged_bindings,
                shared_repository=shared_repository,
                source_commit=source_commit,
                artifact_dir=manual_review_artifact_dir,
                include_normalization_patch=include_normalization_patch,
            )
            if not changed_paths or not run_command(["git", "diff", "--cached", "--name-only"], cwd=local_repo, check=False).strip():
                base_preview.status = "manual_review_required"
                base_preview.message = "Manual-review artifacts produced no staged diff."
                base_preview.review_report_path = report_rel
                base_preview.normalization_patch_path = patch_rel
                return base_preview

            commit_message = build_manual_review_title(shared_repository, source_commit)
            run_command(["git", "commit", "-m", commit_message], cwd=local_repo)
            commit_sha = run_command(["git", "rev-parse", "HEAD"], cwd=local_repo)
            preview_for_pr = ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=base_branch,
                status="would_open_manual_review_pr",
                message="",
                bindings=previews,
                local_repo_path=str(local_repo),
                updater_branch=updater_branch,
                commit_sha=commit_sha,
                review_report_path=report_rel,
                normalization_patch_path=patch_rel,
            )
            if not create_pr:
                preview_for_pr.status = "committed_manual_review_no_pr"
                preview_for_pr.message = "Created a local manual-review commit but PR creation was not requested."
                return preview_for_pr

            pr_title = build_manual_review_title(shared_repository, source_commit)
            pr_body = build_manual_review_body(shared_repository, source_commit, preview_for_pr)
            pr_url, pr_provider = create_pull_request(local_repo, base_branch, updater_branch, pr_title, pr_body)
            preview_for_pr.status = "manual_review_pr_opened"
            preview_for_pr.message = "Opened a manual-review PR for shared-workflow divergence."
            preview_for_pr.pull_request_url = pr_url
            preview_for_pr.pull_request_provider = pr_provider
            return preview_for_pr
        except RuntimeError as exc:
            return ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=base_branch,
                status="pr_creation_failed" if create_pr else "checkout_failed",
                message=str(exc),
                bindings=previews,
                local_repo_path=str(local_repo),
                updater_branch=updater_branch,
            )

    if not candidate_bindings:
        return ConsumerPreview(
            repo=repo_slug,
            resolved_base_branch=base_branch,
            status="no_change",
            message="All impacted managed bindings already match the canonical starter templates.",
            bindings=previews,
            local_repo_path=str(local_repo),
            updater_branch=updater_branch,
        )

    if dry_run or not execute:
        return ConsumerPreview(
            repo=repo_slug,
            resolved_base_branch=base_branch,
            status="would_open_pr",
            message=f"Prepared a preview for {len(candidate_bindings)} managed workflow change(s).",
            bindings=previews,
            local_repo_path=str(local_repo),
            updater_branch=updater_branch,
        )

    try:
        prepare_updater_branch(local_repo, base_branch, updater_branch)
        changed_paths = apply_managed_updates(repo_root, local_repo, candidate_bindings)
        if not changed_paths:
            return ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=base_branch,
                status="no_change",
                message="No effective file changes remained after branch preparation.",
                bindings=previews,
                local_repo_path=str(local_repo),
                updater_branch=updater_branch,
            )

        valid, validation_messages = validate_staged_targets(local_repo, changed_paths)
        if not valid:
            run_command(["git", "reset", "--hard", "HEAD"], cwd=local_repo)
            return ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=base_branch,
                status="validation_failed",
                message="Validation failed for staged workflow updates.",
                bindings=previews,
                local_repo_path=str(local_repo),
                updater_branch=updater_branch,
            )

        if not run_command(["git", "diff", "--cached", "--name-only"], cwd=local_repo, check=False).strip():
            return ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=base_branch,
                status="no_change",
                message="No staged diff remained after applying managed updates.",
                bindings=previews,
                local_repo_path=str(local_repo),
                updater_branch=updater_branch,
            )

        commit_message = build_commit_message(shared_repository, source_commit)
        run_command(["git", "commit", "-m", commit_message], cwd=local_repo)
        commit_sha = run_command(["git", "rev-parse", "HEAD"], cwd=local_repo)

        if not create_pr:
            return ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=base_branch,
                status="committed_no_pr",
                message="Created a local updater commit but PR creation was not requested.",
                bindings=previews,
                local_repo_path=str(local_repo),
                updater_branch=updater_branch,
                commit_sha=commit_sha,
            )

        pr_title = build_pr_title(shared_repository, source_commit)
        pr_body = build_pr_body(
            shared_repository=shared_repository,
            source_commit=source_commit,
            consumer=ConsumerPreview(
                repo=repo_slug,
                resolved_base_branch=base_branch,
                status="would_open_pr",
                message="",
                bindings=previews,
                local_repo_path=str(local_repo),
                updater_branch=updater_branch,
                commit_sha=commit_sha,
            ),
            validation_messages=validation_messages,
        )
        pr_url, pr_provider = create_pull_request(local_repo, base_branch, updater_branch, pr_title, pr_body)
        return ConsumerPreview(
            repo=repo_slug,
            resolved_base_branch=base_branch,
            status="pr_opened",
            message=f"Opened PR for {len(candidate_bindings)} managed workflow change(s).",
            bindings=previews,
            local_repo_path=str(local_repo),
            updater_branch=updater_branch,
            pull_request_url=pr_url,
            pull_request_provider=pr_provider,
            commit_sha=commit_sha,
        )
    except RuntimeError as exc:
        return ConsumerPreview(
            repo=repo_slug,
            resolved_base_branch=base_branch,
            status="pr_creation_failed" if create_pr else "checkout_failed",
            message=str(exc),
            bindings=previews,
            local_repo_path=str(local_repo),
            updater_branch=updater_branch,
        )


def preview_to_dict(preview: ConsumerPreview) -> dict[str, Any]:
    return {
        "repo": preview.repo,
        "resolvedBaseBranch": preview.resolved_base_branch,
        "status": preview.status,
        "message": preview.message,
        "localRepoPath": preview.local_repo_path,
        "updaterBranch": preview.updater_branch,
        "pullRequestUrl": preview.pull_request_url,
        "pullRequestProvider": preview.pull_request_provider,
        "commitSha": preview.commit_sha,
        "reviewReportPath": preview.review_report_path,
        "normalizationPatchPath": preview.normalization_patch_path,
        "bindings": [
            {
                "starterTemplate": binding.starter_template,
                "targetPath": binding.target_path,
                "status": binding.status,
                "message": binding.message,
                "matchedTemplateCommit": binding.matched_template_commit,
                "currentPinnedRefs": binding.current_pinned_refs,
                "candidatePinnedRefs": binding.candidate_pinned_refs,
            }
            for binding in preview.bindings
        ],
    }


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.create_pr:
        args.execute = True

    repo_root = args.repo_root.resolve()
    manifest_path = (repo_root / args.manifest_path).resolve()
    consumer_local_root = args.consumer_local_root.resolve() if args.consumer_local_root else None
    out_summary = (repo_root / args.out_summary).resolve()

    manifest = load_manifest(manifest_path)
    history = StarterTemplateHistory(repo_root)
    changed_templates = resolve_changed_starter_templates(
        repo_root=repo_root,
        previous_source_commit=args.previous_source_commit,
        source_commit=args.source_commit,
        manual_filters=args.starter_template_filter,
    )

    consumer_filter = {item.strip() for item in args.consumer_filter if item.strip()}
    previews: list[ConsumerPreview] = []
    for consumer in manifest.get("consumers", []):
        repo_slug = str(consumer.get("repo") or "").strip()
        if consumer_filter and repo_slug not in consumer_filter:
            continue
        previews.append(
            evaluate_consumer(
                repo_root=repo_root,
                consumer=consumer,
                changed_templates=set(changed_templates),
                consumer_local_root=consumer_local_root,
                history=history,
                source_commit=args.source_commit,
                shared_repository=str(manifest.get("sharedRepository") or ""),
                dry_run=bool(args.dry_run),
                execute=bool(args.execute),
                create_pr=bool(args.create_pr),
                manual_review_on_divergence=bool(args.manual_review_on_divergence),
                manual_review_artifact_dir=str(args.manual_review_artifact_dir),
                include_normalization_patch=bool(args.include_normalization_patch),
                branch_prefix=str(args.branch_prefix),
            )
        )

    summary = {
        "schemaVersion": "1.0.0",
        "sharedRepository": str(manifest.get("sharedRepository") or ""),
        "sourceCommitSha": args.source_commit,
        "previousSourceCommitSha": args.previous_source_commit or None,
        "dryRun": bool(args.dry_run),
        "execute": bool(args.execute),
        "createPr": bool(args.create_pr),
        "manualReviewOnDivergence": bool(args.manual_review_on_divergence),
        "includeNormalizationPatch": bool(args.include_normalization_patch),
        "changedStarterTemplates": changed_templates,
        "consumers": [preview_to_dict(item) for item in previews],
        "limitations": [
            "Remote consumer clone/bootstrap is not implemented yet.",
            "PR creation depends on local consumer clones plus at least one working PR provider/auth path (gh, GitHub REST API token, or GitHub GraphQL token).",
        ],
    }
    write_summary(out_summary, summary)

    impacted = sum(1 for item in previews if item.status not in {"not_impacted"})
    would_open = sum(1 for item in previews if item.status == "would_open_pr")
    would_open_manual = sum(1 for item in previews if item.status == "would_open_manual_review_pr")
    opened = sum(1 for item in previews if item.status in {"pr_opened", "manual_review_pr_opened"})
    manual_review = sum(1 for item in previews if item.status == "manual_review_required")
    print(
        "Prepared cross-repo workflow update run. "
        f"changed_templates={len(changed_templates)} impacted_consumers={impacted} would_open_pr={would_open} "
        f"would_open_manual_review_pr={would_open_manual} opened_pr={opened} manual_review={manual_review} summary={out_summary}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
