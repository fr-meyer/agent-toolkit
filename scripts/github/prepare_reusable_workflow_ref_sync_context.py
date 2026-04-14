#!/usr/bin/env python3
"""
prepare_reusable_workflow_ref_sync_context.py

Builds bounded sync context for deterministic reusable-workflow ref maintenance.

Inputs:
- repo root
- before_sha / after_sha (for diff)
- shared_repo_slug (github.repository or serving repo slug)
- manifest path (required, no default in the simplified source-library layout)

Outputs:
- .tmp/reusable-workflow-ref-sync/context.json

Scope enforcement:
- Only starter workflows listed in the manifest are considered targets.
- Only changes to reusable workflow source files listed in the manifest are considered.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def load_manifest(manifest_path: Path) -> dict:
    """Load and validate the manifest file."""
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to parse manifest: {e}")

    required_keys = {"schemaVersion", "managedWorkflows"}
    if not required_keys.issubset(data.keys()):
        raise SystemExit("Manifest missing required keys: schemaVersion, managedWorkflows")

    for workflow in data.get("managedWorkflows", []):
        workflow["source"] = normalize_path(str(workflow.get("source", "")))
        workflow["publishedWorkflowPath"] = normalize_path(str(workflow.get("publishedWorkflowPath", "")))
        if not workflow["source"] or not workflow["publishedWorkflowPath"]:
            raise SystemExit("Each managedWorkflows entry must include source and publishedWorkflowPath")
        for template in workflow.get("templates", []):
            template["path"] = normalize_path(str(template.get("path", "")))

    return data


def latest_commit_for_path(repo_root: Path, rel_path: str) -> str:
    completed = subprocess.run(
        ["git", "log", "-n", "1", "--format=%H", "--", rel_path],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"Failed to resolve latest commit for {rel_path}: {(completed.stderr or completed.stdout).strip()}")
    sha = (completed.stdout or "").strip()
    if not sha:
        raise SystemExit(f"No commit SHA found for {rel_path}")
    return sha


def resolve_changed_workflows(repo_root: Path, before_sha: str, after_sha: str) -> list[str]:
    """Return list of changed reusable workflow source YAML files."""
    zero = "0" * 40
    if before_sha == zero or before_sha == "":
        changed_files = set()
        for yaml_path in repo_root.glob("templates/reusable-workflows/*.yml"):
            changed_files.add(normalize_path(str(yaml_path.relative_to(repo_root))))
        for yaml_path in repo_root.glob("templates/reusable-workflows/*.yaml"):
            changed_files.add(normalize_path(str(yaml_path.relative_to(repo_root))))
        return sorted(changed_files)

    try:
        diff_cmd = [
            "git",
            "diff",
            "--name-only",
            f"{before_sha}...{after_sha}",
            "--",
            "templates/reusable-workflows/*.yml",
            "templates/reusable-workflows/*.yaml",
        ]
        out = subprocess.check_output(
            diff_cmd,
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
        )
        files = [normalize_path(line.strip()) for line in out.splitlines() if line.strip()]
        return sorted(files)
    except subprocess.CalledProcessError:
        changed_files = set()
        for yaml_path in repo_root.glob("templates/reusable-workflows/*.yml"):
            changed_files.add(normalize_path(str(yaml_path.relative_to(repo_root))))
        for yaml_path in repo_root.glob("templates/reusable-workflows/*.yaml"):
            changed_files.add(normalize_path(str(yaml_path.relative_to(repo_root))))
        return sorted(changed_files)


def build_targets(manifest_data: dict, changed_workflows: list[str], repo_root: Path) -> tuple[list[str], list[dict]]:
    """Determine which starter workflows are targets for the changed reusable workflows."""
    targets: list[str] = []
    target_mappings: list[dict] = []

    for workflow in manifest_data.get("managedWorkflows", []):
        source = workflow.get("source")
        if source not in changed_workflows:
            continue
        expected_sha = latest_commit_for_path(repo_root, source)
        published_workflow_path = workflow.get("publishedWorkflowPath")
        for template in workflow.get("templates", []):
            tpl_path = template.get("path")
            if not tpl_path:
                continue
            targets.append(tpl_path)
            target_mappings.append(
                {
                    "source": source,
                    "publishedWorkflowPath": published_workflow_path,
                    "target": tpl_path,
                    "expectedSha": expected_sha,
                }
            )

    return sorted(set(targets)), target_mappings


def write_context(
    out_dir: Path,
    changed_workflows: list[str],
    targets: list[str],
    target_mappings: list[dict],
    shared_repo_slug: str,
    before_sha: str,
    after_sha: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    context = {
        "changedReusableWorkflows": [{"path": wf, "status": "changed"} for wf in changed_workflows],
        "targetTemplateFiles": targets,
        "targetMappings": target_mappings,
        "sharedRepoSlug": shared_repo_slug,
        "beforeSha": before_sha,
        "afterSha": after_sha,
    }

    (out_dir / "context.json").write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--before", required=True, type=str, help="before SHA")
    parser.add_argument("--after", required=True, type=str, help="after SHA")
    parser.add_argument("--shared-repo-slug", required=True, type=str)
    parser.add_argument("--manifest-path", required=True, type=Path)
    parser.add_argument("--out-dir", default=".tmp/reusable-workflow-ref-sync", type=Path)

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    manifest_path = repo_root / args.manifest_path
    manifest_data = load_manifest(manifest_path)

    changed = resolve_changed_workflows(repo_root, args.before, args.after)
    if not changed:
        print("No reusable workflow source changes detected.")
        return 0

    targets, mappings = build_targets(manifest_data, changed, repo_root)

    write_context(
        (repo_root / args.out_dir).resolve(),
        changed,
        targets,
        mappings,
        args.shared_repo_slug,
        args.before,
        args.after,
    )

    print(f"Prepared context for {len(changed)} changed workflow(s) and {len(targets)} target(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
