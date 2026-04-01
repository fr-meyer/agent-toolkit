#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ISSUES=0
CHECKED=0
OK=0

check_link() {
  local label=$1
  local link_path=$2
  # shellcheck disable=SC2034
  local _expected_target=$3

  CHECKED=$((CHECKED + 1))

  if [ ! -L "$link_path" ] && [ ! -e "$link_path" ]; then
    echo "MISSING  $label ($link_path)"
    ISSUES=$((ISSUES + 1))
    return
  fi

  if [ -L "$link_path" ]; then
    local ACTUAL
    ACTUAL="$(readlink "$link_path")"
    if [ ! -e "$link_path" ]; then
      echo "BROKEN   $label ($link_path → $ACTUAL [target unreachable])"
      ISSUES=$((ISSUES + 1))
      return
    fi
    echo "OK       $label ($link_path → $ACTUAL)"
    OK=$((OK + 1))
  else
    echo "BROKEN   $label ($link_path is a real file/directory, not a symlink)"
    ISSUES=$((ISSUES + 1))
  fi
}

check_link "~/.agent-toolkit" "$HOME/.agent-toolkit" ""
check_link "~/.openclaw/skills" "$HOME/.openclaw/skills" "$HOME/.agent-toolkit/skills"

if [ -n "${1:-}" ]; then
  PROJECT_DIR="$1"
  check_link ".cursor/rules" "$PROJECT_DIR/.cursor/rules" "$HOME/.agent-toolkit/cursor/rules"
elif git rev-parse --show-toplevel >/dev/null 2>&1; then
  PROJECT_DIR="$(pwd)"
  check_link ".cursor/rules" "$PROJECT_DIR/.cursor/rules" "$HOME/.agent-toolkit/cursor/rules"
else
  echo "SKIPPED  .cursor/rules (not a project directory)"
fi

echo "Summary: $CHECKED checked, $OK OK, $ISSUES with issues"
exit $([ "$ISSUES" -eq 0 ] && echo 0 || echo 1)
