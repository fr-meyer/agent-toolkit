#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: ${0##*/} --repo-path <path> --artifact-path <path> --expected-repository <owner/repo> --working-tree-must-be-clean <true|false> --out-dir <path>" >&2
}

REPO_PATH=""
ARTIFACT_PATH=""
EXPECTED_REPOSITORY=""
WORKING_TREE_MUST_BE_CLEAN="true"
OUT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo-path)
      REPO_PATH=${2:-}
      shift 2
      ;;
    --artifact-path)
      ARTIFACT_PATH=${2:-}
      shift 2
      ;;
    --expected-repository)
      EXPECTED_REPOSITORY=${2:-}
      shift 2
      ;;
    --working-tree-must-be-clean)
      WORKING_TREE_MUST_BE_CLEAN=${2:-}
      shift 2
      ;;
    --out-dir)
      OUT_DIR=${2:-}
      shift 2
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

if [ -z "$REPO_PATH" ] || [ -z "$ARTIFACT_PATH" ] || [ -z "$EXPECTED_REPOSITORY" ] || [ -z "$OUT_DIR" ]; then
  usage
  exit 1
fi

mkdir -p "$OUT_DIR"

CURRENT_SHA=""
CURRENT_BRANCH=""
if git -C "$REPO_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  CURRENT_SHA=$(git -C "$REPO_PATH" rev-parse HEAD)
  CURRENT_BRANCH=$(git -C "$REPO_PATH" branch --show-current)
else
  echo "ERROR: $REPO_PATH is not a git working tree" >&2
  exit 1
fi

cat > "$OUT_DIR/preflight-summary.json" <<EOF
{
  "status": "draft-placeholder",
  "repoPath": "$REPO_PATH",
  "artifactPath": "$ARTIFACT_PATH",
  "expectedRepository": "$EXPECTED_REPOSITORY",
  "currentBranch": "$CURRENT_BRANCH",
  "currentSha": "$CURRENT_SHA",
  "workingTreeMustBeClean": "$WORKING_TREE_MUST_BE_CLEAN",
  "note": "Replace this placeholder with repository identity, branch, SHA, and cleanliness checks using actionable-issues.json as the main source of truth."
}
EOF

echo "Draft preflight step complete: wrote $OUT_DIR/preflight-summary.json"
