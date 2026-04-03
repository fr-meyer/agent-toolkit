#!/usr/bin/env bash
set -euo pipefail

resolve_path() {
  local out dir base resolved_dir

  if out=$(readlink -f "$1" 2>/dev/null) && [ -n "$out" ] && [ -e "$out" ]; then
    printf '%s\n' "$out"
    return 0
  fi
  if out=$(python3 -c 'import os, sys
r = os.path.realpath(sys.argv[1])
if os.path.exists(r):
    print(r)
else:
    sys.exit(1)' "$1" 2>/dev/null) && [ -n "$out" ]; then
    printf '%s\n' "$out"
    return 0
  fi
  local path target i
  path=$1
  if [ "${path#/}" = "$path" ]; then
    path="${PWD}/${path}"
  fi
  i=0
  while [ "$i" -lt 64 ]; do
    if [ ! -L "$path" ]; then
      break
    fi
    i=$((i + 1))
    target=$(readlink "$path")
    if [ -z "$target" ]; then
      return 1
    fi
    if [ "${target#/}" = "$target" ]; then
      target="$(dirname "$path")/${target}"
    fi
    path=$target
  done
  if [ -L "$path" ]; then
    return 1
  fi
  if [ ! -e "$path" ]; then
    return 1
  fi
  if ! resolved_dir=$(cd "$(dirname "$path")" && pwd -P 2>/dev/null) || [ -z "$resolved_dir" ]; then
    return 1
  fi
  out="$resolved_dir/$(basename "$path")"
  printf '%s\n' "$out"
  return 0
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

make_absolute() {
  local p=$1
  if [[ "$p" == /* ]]; then
    printf '%s\n' "$p"
  elif [[ "$p" == '~' ]]; then
    printf '%s\n' "$HOME"
  elif [[ "${p:0:2}" == '~/' ]]; then
    printf '%s\n' "${HOME}/${p:2}"
  else
    printf '%s\n' "${PWD}/$p"
  fi
}

usage() {
  echo "Usage: ${0##*/} [--toolkit-root <path>] [--openclaw-home <path>] [--openclaw-scripts-dir <path>] [--cursor-rules-target <path>] [--project-dir <path>] [project-dir]" >&2
}

require_value_for_flag() {
  local flag=$1
  local val=${2:-}
  if [ -z "$val" ]; then
    echo "ERROR: $flag requires a value" >&2
    usage
    exit 1
  fi
  case "$val" in
    -*)
      echo "ERROR: invalid value for $flag (got '$val', which looks like another option)" >&2
      usage
      exit 1
      ;;
  esac
}

FLAG_TOOLKIT_ROOT=""
FLAG_OPENCLAW_HOME=""
FLAG_OPENCLAW_SCRIPTS_DIR=""
FLAG_CURSOR_RULES_TARGET=""
FLAG_PROJECT_DIR=""
POSITIONAL_PROJECT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --toolkit-root)
      require_value_for_flag "$1" "${2:-}"
      FLAG_TOOLKIT_ROOT="$2"
      shift 2
      ;;
    --openclaw-home)
      require_value_for_flag "$1" "${2:-}"
      FLAG_OPENCLAW_HOME="$2"
      shift 2
      ;;
    --openclaw-scripts-dir)
      require_value_for_flag "$1" "${2:-}"
      FLAG_OPENCLAW_SCRIPTS_DIR="$2"
      shift 2
      ;;
    --cursor-rules-target)
      require_value_for_flag "$1" "${2:-}"
      FLAG_CURSOR_RULES_TARGET="$2"
      shift 2
      ;;
    --project-dir)
      require_value_for_flag "$1" "${2:-}"
      FLAG_PROJECT_DIR="$2"
      shift 2
      ;;
    --*)
      usage
      exit 1
      ;;
    *)
      if [ -n "$POSITIONAL_PROJECT_DIR" ]; then
        usage
        exit 1
      fi
      POSITIONAL_PROJECT_DIR="$1"
      shift
      ;;
  esac
done

if [ -n "${FLAG_PROJECT_DIR:-}" ] && [ -n "${POSITIONAL_PROJECT_DIR:-}" ] && [ "$FLAG_PROJECT_DIR" != "$POSITIONAL_PROJECT_DIR" ]; then
  echo "ERROR: --project-dir and positional project path conflict ($FLAG_PROJECT_DIR vs $POSITIONAL_PROJECT_DIR)" >&2
  exit 1
fi

PROJECT_DIR=""
if [ -n "${FLAG_PROJECT_DIR:-}" ]; then
  PROJECT_DIR="$FLAG_PROJECT_DIR"
elif [ -n "${POSITIONAL_PROJECT_DIR:-}" ]; then
  PROJECT_DIR="$POSITIONAL_PROJECT_DIR"
fi

if [ -n "$FLAG_TOOLKIT_ROOT" ]; then
  TOOLKIT_ROOT="$FLAG_TOOLKIT_ROOT"
elif [ -n "${AGENT_TOOLKIT_ROOT:-}" ]; then
  TOOLKIT_ROOT="$AGENT_TOOLKIT_ROOT"
else
  TOOLKIT_ROOT="$HOME/.agent-toolkit"
fi

if [ -n "$FLAG_OPENCLAW_HOME" ]; then
  OPENCLAW_HOME_DIR="$FLAG_OPENCLAW_HOME"
elif [ -n "${OPENCLAW_HOME:-}" ]; then
  OPENCLAW_HOME_DIR="$OPENCLAW_HOME"
else
  OPENCLAW_HOME_DIR="$HOME/.openclaw"
fi

if [ -n "$FLAG_OPENCLAW_SCRIPTS_DIR" ]; then
  OPENCLAW_SCRIPTS_DIR_RAW="$FLAG_OPENCLAW_SCRIPTS_DIR"
elif [ -n "${OPENCLAW_SCRIPTS_DIR:-}" ]; then
  OPENCLAW_SCRIPTS_DIR_RAW="$OPENCLAW_SCRIPTS_DIR"
else
  OPENCLAW_SCRIPTS_DIR_RAW="$OPENCLAW_HOME_DIR/scripts"
fi
OPENCLAW_SCRIPTS_DIR_ABS="$(make_absolute "$OPENCLAW_SCRIPTS_DIR_RAW")"

if [ -n "$FLAG_CURSOR_RULES_TARGET" ]; then
  CURSOR_TARGET="$FLAG_CURSOR_RULES_TARGET"
elif [ -n "${CURSOR_RULES_TARGET:-}" ]; then
  CURSOR_TARGET="$CURSOR_RULES_TARGET"
else
  CURSOR_TARGET="$TOOLKIT_ROOT/cursor/rules"
fi

OPENCLAW_SKILLS="$OPENCLAW_HOME_DIR/skills"
OPENCLAW_SCRIPTS="$OPENCLAW_SCRIPTS_DIR_ABS"

ISSUES=0
CHECKED=0
OK=0

check_toolkit_root() {
  local label=$1
  local path=$2

  CHECKED=$((CHECKED + 1))

  if [ ! -e "$path" ] && [ ! -L "$path" ]; then
    echo "MISSING  $label ($path)"
    ISSUES=$((ISSUES + 1))
    return
  fi

  if [ -L "$path" ]; then
    if [ ! -d "$path" ]; then
      local ACTUAL
      ACTUAL="$(readlink "$path")"
      echo "BROKEN   $label ($path → $ACTUAL [target unreachable or not a directory])"
      ISSUES=$((ISSUES + 1))
      return
    fi
    local ACTUAL
    ACTUAL="$(readlink "$path")"
    echo "OK       $label ($path → $ACTUAL) (symlink)"
    OK=$((OK + 1))
    return
  fi

  if [ -d "$path" ]; then
    echo "OK       $label ($path) (directory)"
    OK=$((OK + 1))
    return
  fi

  echo "BROKEN   $label ($path exists but is not a directory)"
  ISSUES=$((ISSUES + 1))
}

check_link() {
  local label=$1
  local link_path=$2
  local expected_target=$3

  CHECKED=$((CHECKED + 1))

  if [ ! -L "$link_path" ] && [ ! -e "$link_path" ]; then
    echo "MISSING  $label ($link_path)"
    ISSUES=$((ISSUES + 1))
    return
  fi

  if [ -L "$link_path" ]; then
    local ACTUAL actual_canon expected_canon
    ACTUAL="$(readlink "$link_path")"
    if [ ! -e "$link_path" ]; then
      echo "BROKEN   $label ($link_path → $ACTUAL [target unreachable])"
      ISSUES=$((ISSUES + 1))
      return
    fi
    if [ -n "$expected_target" ]; then
      actual_canon="$(resolve_path "$link_path" || true)"
      expected_canon="$(resolve_path "$expected_target" || true)"
      if [ -z "$expected_canon" ]; then
        echo "BROKEN   $label ($link_path → $ACTUAL; expected target $expected_target could not be resolved)"
        ISSUES=$((ISSUES + 1))
        return
      fi
      if [ "$actual_canon" != "$expected_canon" ]; then
        echo "BROKEN   $label ($link_path → $ACTUAL; expected $expected_target) [resolved actual: $actual_canon, resolved expected: $expected_canon]"
        ISSUES=$((ISSUES + 1))
        return
      fi
    fi
    echo "OK       $label ($link_path → $ACTUAL)"
    OK=$((OK + 1))
  else
    echo "BROKEN   $label ($link_path is a real file/directory, not a symlink)"
    ISSUES=$((ISSUES + 1))
  fi
}

check_toolkit_root "toolkit-root" "$TOOLKIT_ROOT"
check_link "openclaw/skills" "$OPENCLAW_SKILLS" "$TOOLKIT_ROOT/skills"
check_link "openclaw/scripts" "$OPENCLAW_SCRIPTS" "$TOOLKIT_ROOT/scripts"

if [ -n "${PROJECT_DIR:-}" ]; then
  check_link ".cursor/rules" "$PROJECT_DIR/.cursor/rules" "$CURSOR_TARGET"
elif git rev-parse --show-toplevel >/dev/null 2>&1; then
  check_link ".cursor/rules" "$(pwd)/.cursor/rules" "$CURSOR_TARGET"
else
  echo "SKIPPED  .cursor/rules (not a project directory)"
fi

echo "Summary: $CHECKED checked, $OK OK, $ISSUES with issues"
exit $([ "$ISSUES" -eq 0 ] && echo 0 || echo 1)
