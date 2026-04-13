#!/usr/bin/env python3
"""
validate_reusable_workflow_refs.py

Validates that all target templates have been updated correctly.

Scope enforcement:
- Only templates listed in the context targetTemplateFiles are validated.
- Only reusable workflow calls explicitly listed in targetMappings are checked.
- Only the paired shared_repository_ref is checked.
- Fails if any mismatch is found.
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


def find_target_calls(template_path: Path, shared_repo_slug: str, source_workflow_path: str) -> list[tuple[int, str, str | None]]:
    """Return (line_no, uses_ref, shared_repository_ref)."""
    uses_pattern = re.compile(
        rf"^\s*uses:\s*{re.escape(shared_repo_slug)}/{re.escape(source_workflow_path)}@([^\s#]+)\s*$"
    )
    shared_ref_pattern = re.compile(r"^\s*shared_repository_ref:\s*(\S+)\s*$")

    lines = template_path.read_text(encoding="utf-8").splitlines()
    matches: list[tuple[int, str, str | None]] = []

    for idx, raw in enumerate(lines):
        uses_match = uses_pattern.match(raw)
        if not uses_match:
            continue

        uses_ref = uses_match.group(1).strip().strip('"').strip("'")
        shared_ref = None
        uses_indent = len(raw) - len(raw.lstrip(" "))

        for j in range(idx + 1, len(lines)):
            next_raw = lines[j]
            next_stripped = next_raw.strip()
            next_indent = len(next_raw) - len(next_raw.lstrip(" "))

            if next_stripped.startswith("uses:") and next_indent <= uses_indent:
                break

            shared_match = shared_ref_pattern.match(next_raw)
            if shared_match:
                shared_ref = shared_match.group(1).strip().strip('"').strip("'")
                break

        matches.append((idx + 1, uses_ref, shared_ref))

    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--context", required=True, type=Path, help="path to .ai-sync-context/context.json")

    args = parser.parse_args()

    ctx = load_context(args.context)
    shared_repo_slug = str(ctx.get("sharedRepoSlug") or "").strip()
    targets = ctx.get("targetTemplateFiles", [])
    mappings = ctx.get("targetMappings", [])

    if not shared_repo_slug:
        raise SystemExit("Context is missing sharedRepoSlug")

    if not targets or not mappings:
        print("No target templates to validate.")
        return 0

    repo_root = args.repo_root.resolve()
    ok = True

    for mapping in mappings:
        source = str(mapping.get("source") or "").strip()
        target = str(mapping.get("target") or "").strip()
        expected_sha = str(mapping.get("expectedSha") or "").strip()

        if not source or not target or not expected_sha:
            print("Invalid target mapping entry (missing source/target/expectedSha).")
            ok = False
            continue
        if not SHA_RE.fullmatch(expected_sha):
            print(f"Invalid expected SHA for {target}: {expected_sha}")
            ok = False
            continue

        tpl_path = repo_root / target
        if not tpl_path.exists():
            print(f"Target template missing: {target}")
            ok = False
            continue

        print(f"Validating {target} against {source} -> {expected_sha}")
        matches = find_target_calls(tpl_path, shared_repo_slug, source)
        if not matches:
            print(f"  - {target}: no matching reusable workflow call found")
            ok = False
            continue

        for line_no, uses_ref, shared_ref in matches:
            if not SHA_RE.fullmatch(uses_ref):
                print(f"  - {target}:{line_no} uses ref is not a pinned SHA: {uses_ref}")
                ok = False
            elif uses_ref != expected_sha:
                print(f"  - {target}:{line_no} uses ref mismatch: {uses_ref} != {expected_sha}")
                ok = False

            if shared_ref is None:
                print(f"  - {target}:{line_no} missing paired shared_repository_ref")
                ok = False
            elif not SHA_RE.fullmatch(shared_ref):
                print(f"  - {target}:{line_no} shared_repository_ref is not a pinned SHA: {shared_ref}")
                ok = False
            elif shared_ref != expected_sha:
                print(f"  - {target}:{line_no} shared_repository_ref mismatch: {shared_ref} != {expected_sha}")
                ok = False

    if ok:
        print("All validations passed.")
        return 0

    raise SystemExit("Validation failed: mismatched refs found.")


if __name__ == "__main__":
    sys.exit(main())
