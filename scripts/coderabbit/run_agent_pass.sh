#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: ${0##*/} --repo-path <path> --shared-root <path> --pr-number <number> --out-dir <path>" >&2
}

REPO_PATH=""
SHARED_ROOT=""
PR_NUMBER=""
OUT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo-path)
      REPO_PATH=${2:-}
      shift 2
      ;;
    --shared-root)
      SHARED_ROOT=${2:-}
      shift 2
      ;;
    --pr-number)
      PR_NUMBER=${2:-}
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

if [ -z "$REPO_PATH" ] || [ -z "$SHARED_ROOT" ] || [ -z "$PR_NUMBER" ] || [ -z "$OUT_DIR" ]; then
  usage
  exit 1
fi

mkdir -p "$OUT_DIR"

cat > "$OUT_DIR/agent-pass-summary.txt" <<EOF
Draft placeholder only.

Future implementation should invoke the chosen agent runtime with:
- repo path: $REPO_PATH
- shared root: $SHARED_ROOT
- PR number: $PR_NUMBER
- normalized artifact: $OUT_DIR/actionable-issues.json

The runtime prompt should keep work bounded to the extracted unresolved CodeRabbit issue set.
EOF

echo "Draft agent-pass step complete: wrote $OUT_DIR/agent-pass-summary.txt"
