#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: ${0##*/} --repo-path <path> --shared-root <path> --pr-number <number> --run-validation <true|false> --out-dir <path>" >&2
}

REPO_PATH=""
SHARED_ROOT=""
PR_NUMBER=""
RUN_VALIDATION="true"
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
    --run-validation)
      RUN_VALIDATION=${2:-}
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

bash "$SHARED_ROOT/scripts/coderabbit/run_agent_pass.sh" \
  --repo-path "$REPO_PATH" \
  --shared-root "$SHARED_ROOT" \
  --pr-number "$PR_NUMBER" \
  --out-dir "$OUT_DIR"

if [ "$RUN_VALIDATION" = "true" ]; then
  bash "$SHARED_ROOT/scripts/coderabbit/run_validation.sh" \
    --repo-path "$REPO_PATH" \
    --pr-number "$PR_NUMBER" \
    --out-dir "$OUT_DIR"
fi

cat > "$OUT_DIR/orchestration-summary.json" <<EOF
{
  "status": "draft-placeholder",
  "repoPath": "$REPO_PATH",
  "sharedRoot": "$SHARED_ROOT",
  "prNumber": "$PR_NUMBER",
  "runValidation": "$RUN_VALIDATION",
  "note": "Replace this placeholder with bounded multi-cycle orchestration, stop rules, and validation-rate-limit handling."
}
EOF

echo "Draft orchestration step complete: wrote $OUT_DIR/orchestration-summary.json"
