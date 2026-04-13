#!/usr/bin/env bash
set -euo pipefail

REPO_PATH=""
SHARED_ROOT=""
OUT_DIR=""
INSTALL_SHARED_SKILLS="true"
INSTALL_CURSOR_RULES="true"
INSTALL_MODE="copy"

usage() {
  cat >&2 <<'EOF'
Usage: prepare_agent_context.sh \
  --repo-path <path> \
  --shared-root <path> \
  --out-dir <path> \
  --install-shared-skills <true|false> \
  --install-cursor-rules <true|false> \
  --install-mode <copy|symlink>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-path)
      REPO_PATH="${2:-}"
      shift 2
      ;;
    --shared-root)
      SHARED_ROOT="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --install-shared-skills)
      INSTALL_SHARED_SKILLS="${2:-}"
      shift 2
      ;;
    --install-cursor-rules)
      INSTALL_CURSOR_RULES="${2:-}"
      shift 2
      ;;
    --install-mode)
      INSTALL_MODE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$REPO_PATH" || -z "$SHARED_ROOT" || -z "$OUT_DIR" ]]; then
  echo "ERROR: --repo-path, --shared-root, and --out-dir are required." >&2
  usage
  exit 1
fi

case "$INSTALL_SHARED_SKILLS" in
  true|false) ;;
  *)
    echo "ERROR: --install-shared-skills must be true or false." >&2
    exit 1
    ;;
esac

case "$INSTALL_CURSOR_RULES" in
  true|false) ;;
  *)
    echo "ERROR: --install-cursor-rules must be true or false." >&2
    exit 1
    ;;
esac

case "$INSTALL_MODE" in
  copy|symlink) ;;
  *)
    echo "ERROR: --install-mode must be one of: copy, symlink." >&2
    exit 1
    ;;
esac

REPO_PATH=$(cd "$REPO_PATH" && pwd)
SHARED_ROOT=$(cd "$SHARED_ROOT" && pwd)
mkdir -p "$OUT_DIR"
OUT_DIR=$(cd "$OUT_DIR" && pwd)

if [[ ! -d "$REPO_PATH" ]]; then
  echo "ERROR: repo path is not a directory: $REPO_PATH" >&2
  exit 1
fi

if [[ ! -d "$SHARED_ROOT" ]]; then
  echo "ERROR: shared root is not a directory: $SHARED_ROOT" >&2
  exit 1
fi

SHARED_SKILLS_SOURCE="$SHARED_ROOT/skills"
CURSOR_RULES_SOURCE="$SHARED_ROOT/cursor/rules"
SHARED_SKILLS_TARGET="$REPO_PATH/.agents/skills"
CURSOR_RULES_TARGET="$REPO_PATH/.cursor/rules"

STATUS="ready"
ERROR_MESSAGE=""

count_skills() {
  python - "$1" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
count = 0
if root.exists():
    for child in root.iterdir():
        if child.is_dir() and (child / "SKILL.md").is_file():
            count += 1
print(count)
PY
}

count_rules() {
  python - "$1" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
count = 0
if root.exists():
    count = sum(1 for p in root.rglob("*.mdc") if p.is_file())
print(count)
PY
}

write_summary() {
  local shared_exists="false"
  local cursor_exists="false"
  local skill_count="0"
  local rule_count="0"

  if [[ -e "$SHARED_SKILLS_TARGET" ]]; then
    shared_exists="true"
    skill_count=$(count_skills "$SHARED_SKILLS_TARGET")
  fi

  if [[ -e "$CURSOR_RULES_TARGET" ]]; then
    cursor_exists="true"
    rule_count=$(count_rules "$CURSOR_RULES_TARGET")
  fi

  python - <<PY
from pathlib import Path
import json

out_dir = Path(r"$OUT_DIR")
payload = {
    "status": "$STATUS",
    "repoPath": r"$REPO_PATH",
    "sharedRoot": r"$SHARED_ROOT",
    "installMode": "$INSTALL_MODE",
    "sharedSkills": {
        "enabled": "$INSTALL_SHARED_SKILLS".lower() == "true",
        "source": r"$SHARED_SKILLS_SOURCE",
        "target": r"$SHARED_SKILLS_TARGET",
        "exists": "$shared_exists".lower() == "true",
        "skillCount": int("$skill_count"),
    },
    "cursorRules": {
        "enabled": "$INSTALL_CURSOR_RULES".lower() == "true",
        "source": r"$CURSOR_RULES_SOURCE",
        "target": r"$CURSOR_RULES_TARGET",
        "exists": "$cursor_exists".lower() == "true",
        "ruleCount": int("$rule_count"),
    },
    "note": r"$ERROR_MESSAGE" if "$ERROR_MESSAGE" else None,
    "metadata": {
        "source": "prepare_agent_context.sh",
    },
}
(out_dir / "agent-context-summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

lines = [
    f"status: {payload['status']}",
    f"repo path: {payload['repoPath']}",
    f"shared root: {payload['sharedRoot']}",
    f"install mode: {payload['installMode']}",
    f"shared skills enabled: {payload['sharedSkills']['enabled']}",
    f"shared skills target: {payload['sharedSkills']['target']}",
    f"shared skills exists: {payload['sharedSkills']['exists']}",
    f"shared skills count: {payload['sharedSkills']['skillCount']}",
    f"cursor rules enabled: {payload['cursorRules']['enabled']}",
    f"cursor rules target: {payload['cursorRules']['target']}",
    f"cursor rules exists: {payload['cursorRules']['exists']}",
    f"cursor rules count: {payload['cursorRules']['ruleCount']}",
]
if payload["note"]:
    lines.extend(["", f"note: {payload['note']}"])
(out_dir / "agent-context-summary.txt").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
PY
}

on_error() {
  trap - ERR
  STATUS="error"
  write_summary || true
  exit 1
}

trap 'ERROR_MESSAGE="Command failed on line $LINENO: $BASH_COMMAND"; on_error' ERR

install_path() {
  local enabled="$1"
  local source="$2"
  local target="$3"

  if [[ "$enabled" != "true" ]]; then
    return 0
  fi

  if [[ ! -d "$source" ]]; then
    echo "ERROR: expected source directory is missing: $source" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$target")"
  rm -rf "$target"

  if [[ "$INSTALL_MODE" == "copy" ]]; then
    cp -R "$source" "$target"
  else
    ln -s "$source" "$target"
  fi
}

install_path "$INSTALL_SHARED_SKILLS" "$SHARED_SKILLS_SOURCE" "$SHARED_SKILLS_TARGET"
install_path "$INSTALL_CURSOR_RULES" "$CURSOR_RULES_SOURCE" "$CURSOR_RULES_TARGET"

trap - ERR
STATUS="ready"
write_summary

echo "Prepared shared agent context:"
cat "$OUT_DIR/agent-context-summary.txt"
