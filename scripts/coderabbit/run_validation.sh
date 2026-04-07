#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: ${0##*/} --repo-path <path> --pr-number <number> --out-dir <path>" >&2
}

REPO_PATH=""
PR_NUMBER=""
OUT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo-path)
      REPO_PATH=${2:-}
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

if [ -z "$REPO_PATH" ] || [ -z "$PR_NUMBER" ] || [ -z "$OUT_DIR" ]; then
  usage
  exit 1
fi

mkdir -p "$OUT_DIR"

cat > "$OUT_DIR/validation-result.json" <<EOF
{
  "status": "draft-placeholder",
  "repoPath": "$REPO_PATH",
  "prNumber": "$PR_NUMBER",
  "note": "Replace this placeholder with CodeRabbit CLI invocation and validation-result capture."
}
EOF

echo "Draft validation step complete: wrote $OUT_DIR/validation-result.json"
