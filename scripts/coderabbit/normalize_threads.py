#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def git_output(repo_path: str, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", repo_path, *args],
        text=True,
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--repo-name", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--in-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    branch = git_output(args.repo_path, "branch", "--show-current") or "draft-placeholder-branch"
    head_sha = git_output(args.repo_path, "rev-parse", "HEAD")

    artifact = {
        "pr": {
            "number": int(args.pr_number),
            "title": "Draft placeholder PR title",
            "branch": branch,
            "repository": args.repo_name,
            "headSha": head_sha,
        },
        "constraints": {
            "maxCycles": 3,
            "allowCommit": False,
            "allowPush": False,
            "allowPrComment": False,
            "allowThreadResolution": False,
            "allowScopeExpansion": False,
        },
        "context": {
            "repoPath": args.repo_path,
            "expectedRepository": args.repo_name,
            "expectedBranch": branch,
            "expectedHeadSha": head_sha,
            "workingTreeMustBeClean": True,
        },
        "issues": [],
        "metadata": {
            "artifactVersion": "draft-v1",
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "draft-normalize-threads-placeholder",
        },
    }

    (out_dir / "actionable-issues.json").write_text(
        json.dumps(artifact, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Draft normalization step complete: wrote {out_dir / 'actionable-issues.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
