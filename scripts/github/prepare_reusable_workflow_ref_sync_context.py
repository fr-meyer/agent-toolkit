#!/usr/bin/env python3
"""
Prepare bounded context for an AI agent that updates starter-template pinned refs.

CLI:
  python scripts/github/prepare_reusable_workflow_ref_sync_context.py \
    --repo-root . \
    --before 0000000000000000000000000000000000000000 \
    --after 39a84b813769663a445cdeac62322ffd2ee8a435 \
    --shared-repo-slug fr-meyer/agent-toolkit \
    --out-dir .github/workflows/.ai-sync-context

Environment overrides (optional):
  - WORKFLOW_REF_SYNC_CONTEXT_DIR
  - WORKFLOW_REF_SYNC_SHA_BEFORE
  - WORKFLOW_REF_SYNC_SHA_AFTER
  - WORKFLOW_REF_SYNC_SHARED_REPO

Exit codes:
  0  – context prepared successfully
  1  – misconfiguration or runtime error
"""

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import List


SHA_ZERO = "0" * 40


def git_output(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(stderr or f"git {' '.join(args)} failed with code {completed.returncode}")
    return (completed.stdout or "").rstrip("\r\n")


def git_try(repo_path: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return (completed.stdout or "").rstrip("\r\n")


def changed_workflow_files(repo_path: Path, before: str, after: str) -> List[Path]:
    if before == SHA_ZERO:
        names = git_output(repo_path, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", after).splitlines()
    else:
        names = git_output(repo_path, "diff", "--name-only", f"{before}..{after}").splitlines()

    paths = [repo_path / name.strip() for name in names if name.strip()]
    return [
        p for p in paths
        if p.suffix.lower() in (".yml", ".yaml")
        and ".github/workflows" in p.relative_to(repo_path).as_posix()
    ]


def latest_commit_for_path(repo_path: Path, path: Path) -> str:
    sha = git_output(repo_path, "log", "-n", "1", "--format=%H", "--", str(path.relative_to(repo_path)))
    return sha.strip()


def template_files(repo_path: Path) -> List[Path]:
    tmpl_dir = repo_path / ".github" / "workflow-templates"
    if not tmpl_dir.is_dir():
        return []
    paths = []
    for suffix in (".yml", ".yaml"):
        paths.extend(tmpl_dir.glob(f"*{suffix}"))
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare context for AI ref-sync workflow.")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--before", default=os.environ.get("WORKFLOW_REF_SYNC_SHA_BEFORE", SHA_ZERO))
    parser.add_argument("--after", default=os.environ.get("WORKFLOW_REF_SYNC_SHA_AFTER", git_output(Path("."), "rev-parse", "HEAD")))
    parser.add_argument("--shared-repo-slug", default=os.environ.get("WORKFLOW_REF_SYNC_SHARED_REPO", "fr-meyer/agent-toolkit"))
    parser.add_argument("--out-dir", type=Path, default=Path(os.environ.get("WORKFLOW_REF_SYNC_CONTEXT_DIR", ".github/workflows/.ai-sync-context")))

    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    changed = changed_workflow_files(args.repo_root, args.before, args.after)

    context = {
        "sharedRepoSlug": args.shared_repo_slug,
        "changedReusableWorkflows": [],
        "templateFiles": [],
        "managedMarker": "managed-shared-workflow-ref",
    }

    # Build changed reusable workflows list
    for wf in changed:
        expected_sha = latest_commit_for_path(args.repo_root, wf)
        context["changedReusableWorkflows"].append({
            "path": wf.relative_to(args.repo_root).as_posix(),
            "expectedSha": expected_sha,
        })

    # Enumerate template files
    for tmpl in template_files(args.repo_root):
        context["templateFiles"].append(tmpl.relative_to(args.repo_root).as_posix())

    # Write context.json
    (out_dir / "context.json").write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")

    # Write prompt.txt
    prompt_lines = [
        "You are an AI assistant tasked with keeping starter-template pinned refs in sync.",
        "",
        "Instructions:",
        "- Work only inside .github/workflow-templates/**",
        "- Inspect changed reusable workflows listed in context.json",
        "- For each template file:",
        "  - Find managed-shared-workflow-ref markers",
        "  - For each managed reusable-workflow call:",
        "    - Update the uses: ref to the expectedSha from context.json",
        "    - Update the paired shared_repository_ref to the same SHA",
        "- Preserve unrelated formatting and content",
        "- Make no edits if no template refs are impacted",
        "",
        "Return a concise summary of what you changed.",
    ]
    (out_dir / "prompt.txt").write_text("\n".join(prompt_lines) + "\n", encoding="utf-8")

    print(f"Prepared AI ref-sync context in {out_dir}")
    print(f"- changed reusable workflows: {len(context['changedReusableWorkflows'])}")
    print(f"- template files: {len(context['templateFiles'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
