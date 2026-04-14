#!/usr/bin/env python3
"""
materialize_repo_workflow_templates.py

Deterministically copies canonical repo-maintenance workflow source assets from
`templates/` into their live repo-local `.github/workflows/` targets.
"""

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--manifest-path", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    manifest_path = (repo_root / args.manifest_path).resolve()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    workflows = manifest.get("workflows") or []
    if not isinstance(workflows, list):
        raise SystemExit("Manifest key 'workflows' must be a list.")

    changed = 0
    for item in workflows:
        if not isinstance(item, dict):
            raise SystemExit("Each workflow mapping must be an object.")
        source_rel = item.get("source")
        target_rel = item.get("target")
        if not source_rel or not target_rel:
            raise SystemExit("Each workflow mapping requires 'source' and 'target'.")

        source_path = (repo_root / source_rel).resolve()
        target_path = (repo_root / target_rel).resolve()

        if not str(source_path).startswith(str(repo_root)):
            raise SystemExit(f"Source path escapes repo root: {source_rel}")
        if not str(target_path).startswith(str(repo_root)):
            raise SystemExit(f"Target path escapes repo root: {target_rel}")
        if not source_rel.startswith("templates/repo-maintenance-workflows/"):
            raise SystemExit(f"Source must live under templates/repo-maintenance-workflows/: {source_rel}")
        if not target_rel.startswith(".github/workflows/"):
            raise SystemExit(f"Target must live under .github/workflows/: {target_rel}")

        source_text = source_path.read_text(encoding="utf-8")
        target_text = target_path.read_text(encoding="utf-8") if target_path.exists() else None

        if target_text != source_text:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(source_text, encoding="utf-8")
            changed += 1
            print(f"Materialized {target_rel} from {source_rel}: changed=yes")
        else:
            print(f"Materialized {target_rel} from {source_rel}: changed=no")

    print(f"Done. workflows_changed={changed}")


if __name__ == "__main__":
    main()
