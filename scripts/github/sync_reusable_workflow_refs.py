#!/usr/bin/env python3
"""
sync_reusable_workflow_refs.py

Deterministically updates pinned reusable-workflow refs in starter workflow
source assets based on the bounded context prepared by
prepare_reusable_workflow_ref_sync_context.py.

Scope enforcement:
- Only starter workflows listed in context targetTemplateFiles are modified.
- Only reusable workflow calls explicitly listed in targetMappings are updated.
- Only the matching uses: line and the paired shared_repository_ref are changed.
"""

import argparse
import json
import re
import sys
from pathlib import Path


SHA_RE = re.compile(r"^[a-f0-9]{40}$")


def load_context(context_path: Path) -> dict:
    if not context_path.exists():
        raise SystemExit(f"Context not found: {context_path}")
    try:
        return json.loads(context_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to parse context: {e}")


def replace_ref_token(raw: str, old_ref: str, expected_sha: str) -> str:
    old_variants = [f"@{old_ref}", f'@"{old_ref}"', f"@'{old_ref}'"]
    new_variants = [f"@{expected_sha}", f'@"{expected_sha}"', f"@'{expected_sha}'"]
    for old, new in zip(old_variants, new_variants):
        if old in raw:
            return raw.replace(old, new, 1)
    raise SystemExit(f"Unable to replace uses ref in line: {raw.strip()}")


def replace_shared_ref_value(raw: str, expected_sha: str) -> str:
    match = re.match(r"^(\s*shared_repository_ref:\s*)(\S+)(\s*)$", raw)
    if not match:
        raise SystemExit(f"Unable to parse shared_repository_ref line: {raw.strip()}")
    prefix, value, suffix = match.groups()
    unquoted = value.strip().strip('"').strip("'")
    quoted = value != unquoted
    if value.startswith('"') and value.endswith('"'):
        new_value = f'"{expected_sha}"'
    elif value.startswith("'") and value.endswith("'"):
        new_value = f"'{expected_sha}'"
    else:
        new_value = expected_sha
    return f"{prefix}{new_value}{suffix}"


def update_target_file(template_path: Path, shared_repo_slug: str, published_workflow_path: str, expected_sha: str) -> tuple[bool, int]:
    if not SHA_RE.fullmatch(expected_sha):
        raise SystemExit(f"Invalid expected SHA: {expected_sha}")

    lines = template_path.read_text(encoding="utf-8").splitlines(keepends=True)
    uses_pattern = re.compile(
        rf"^(\s*uses:\s*{re.escape(shared_repo_slug)}/{re.escape(published_workflow_path)}@)([^\s#]+)(\s*)$"
    )
    shared_ref_pattern = re.compile(r"^\s*shared_repository_ref:\s*(\S+)\s*$")

    changed = False
    updates = 0

    for idx, raw in enumerate(lines):
        match = uses_pattern.match(raw.rstrip("\n"))
        if not match:
            continue

        current_ref = match.group(2).strip().strip('"').strip("'")
        if current_ref != expected_sha:
            lines[idx] = replace_ref_token(raw.rstrip("\n"), current_ref, expected_sha) + ("\n" if raw.endswith("\n") else "")
            changed = True

        uses_indent = len(raw) - len(raw.lstrip(" "))
        found_shared_ref = False

        for j in range(idx + 1, len(lines)):
            next_raw = lines[j]
            next_stripped = next_raw.strip()
            next_indent = len(next_raw) - len(next_raw.lstrip(" "))

            if next_stripped.startswith("uses:") and next_indent <= uses_indent:
                break

            if shared_ref_pattern.match(next_raw.rstrip("\n")):
                found_shared_ref = True
                shared_value = shared_ref_pattern.match(next_raw.rstrip("\n")).group(1).strip().strip('"').strip("'")
                if shared_value != expected_sha:
                    lines[j] = replace_shared_ref_value(next_raw.rstrip("\n"), expected_sha) + ("\n" if next_raw.endswith("\n") else "")
                    changed = True
                updates += 1
                break

        if not found_shared_ref:
            raise SystemExit(
                f"Missing paired shared_repository_ref for {template_path} near uses call for {published_workflow_path}"
            )

    if updates == 0:
        raise SystemExit(f"No matching reusable workflow call found in {template_path} for {published_workflow_path}")

    if changed:
        template_path.write_text("".join(lines), encoding="utf-8")

    return changed, updates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--context", required=True, type=Path, help="path to context.json")

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    ctx = load_context(args.context)
    shared_repo_slug = str(ctx.get("sharedRepoSlug") or "").strip()
    mappings = ctx.get("targetMappings", [])

    if not shared_repo_slug:
        raise SystemExit("Context is missing sharedRepoSlug")

    if not mappings:
        print("No target starter workflows to update.")
        return 0

    total_files_changed = 0
    total_calls_updated = 0

    for mapping in mappings:
        target = str(mapping.get("target") or "").strip()
        published_workflow_path = str(mapping.get("publishedWorkflowPath") or "").strip()
        expected_sha = str(mapping.get("expectedSha") or "").strip()

        if not target or not published_workflow_path or not expected_sha:
            raise SystemExit("Invalid target mapping entry (missing target/publishedWorkflowPath/expectedSha).")

        tpl_path = repo_root / target
        if not tpl_path.exists():
            raise SystemExit(f"Target starter workflow missing: {target}")

        changed, updates = update_target_file(tpl_path, shared_repo_slug, published_workflow_path, expected_sha)
        if changed:
            total_files_changed += 1
        total_calls_updated += updates
        print(f"Processed {target}: calls={updates}, changed={'yes' if changed else 'no'}")

    print(f"Done. files_changed={total_files_changed} calls_updated={total_calls_updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
