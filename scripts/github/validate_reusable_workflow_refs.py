#!/usr/bin/env python3
"""
Deterministic post-AI guardrail to validate pinned reusable-workflow refs.

CLI:
  python scripts/github/validate_reusable_workflow_refs.py \
    --repo-root . \
    --context .github/workflows/.ai-sync-context/context.json

Exit codes:
  0  – validation passed
  1  – validation failed or error
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def normalize_path(value: str) -> str:
    return value.replace("\\", "/")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_valid_sha(s: str) -> bool:
    return bool(SHA_RE.fullmatch(s))


def find_managed_blocks(content: str) -> List[Dict[str, Any]]:
    blocks = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("# managed-shared-workflow-ref:") or line.startswith("#managed-shared-workflow-ref:"):
            marker = line.split(":", 1)[1].strip()
            j = i + 1
            uses_sha = None
            shared_ref = None
            while j < len(lines):
                l2 = lines[j].strip()
                if j > i + 1 and (l2.startswith("# managed-shared-workflow-ref:") or l2.startswith("#managed-shared-workflow-ref:")):
                    break
                if uses_sha is None and l2.startswith("uses:"):
                    parts = l2.split("@", 1)
                    if len(parts) == 2:
                        uses_sha = parts[1].strip()
                if shared_ref is None and l2.startswith("shared_repository_ref:"):
                    kv = l2.split(":", 1)
                    if len(kv) == 2:
                        shared_ref = kv[1].strip()
                if uses_sha is not None and shared_ref is not None:
                    break
                j += 1
            blocks.append({
                "marker": marker,
                "usesSha": uses_sha,
                "sharedRef": shared_ref,
                "line": i + 1,
            })
            i = j
        else:
            i += 1
    return blocks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pinned reusable-workflow refs.")
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--context", required=True, type=Path)

    args = parser.parse_args()

    ctx = load_json(args.context)
    changed = ctx.get("changedReusableWorkflows") or []
    templates = ctx.get("templateFiles") or []

    errors: List[str] = []

    for tmpl_rel in templates:
        tmpl_path = args.repo_root / tmpl_rel
        if not tmpl_path.exists():
            continue
        content = tmpl_path.read_text(encoding="utf-8")
        blocks = find_managed_blocks(content)
        for block in blocks:
            expected_sha = None
            normalized_marker = normalize_path(block["marker"])
            for wf in changed:
                if normalize_path(str(wf.get("path", ""))) == normalized_marker:
                    expected_sha = wf.get("expectedSha")
                    break
            if not expected_sha:
                errors.append(f"{tmpl_rel}:{block['line']}: managed marker '{block['marker']}' not found in changed workflows")
                continue
            if not is_valid_sha(expected_sha):
                errors.append(f"{tmpl_rel}:{block['line']}: expectedSha '{expected_sha}' is not a valid SHA")
                continue
            if not block["usesSha"]:
                errors.append(f"{tmpl_rel}:{block['line']}: missing uses ref after managed marker")
            elif not is_valid_sha(block["usesSha"]):
                errors.append(f"{tmpl_rel}:{block['line']}: uses ref '{block['usesSha']}' is not a valid SHA")
            elif block["usesSha"] != expected_sha:
                errors.append(f"{tmpl_rel}:{block['line']}: uses ref '{block['usesSha']}' != expected '{expected_sha}'")

            if not block["sharedRef"]:
                errors.append(f"{tmpl_rel}:{block['line']}: missing shared_repository_ref after managed marker")
            elif not is_valid_sha(block["sharedRef"]):
                errors.append(f"{tmpl_rel}:{block['line']}: shared_repository_ref '{block['sharedRef']}' is not a valid SHA")
            elif block["sharedRef"] != expected_sha:
                errors.append(f"{tmpl_rel}:{block['line']}: shared_repository_ref '{block['sharedRef']}' != expected '{expected_sha}'")

    if errors:
        summary_path = args.context.parent / "validation-errors.txt"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text("\n".join(errors) + "\n", encoding="utf-8")
        print("Validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1

    print("Validation passed: all managed refs are pinned and aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
