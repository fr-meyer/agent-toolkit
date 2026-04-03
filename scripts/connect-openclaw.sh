#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  echo "Usage: ${0##*/} [--toolkit-root <path>] [--openclaw-home <path>] [--openclaw-scripts-dir <path>] [--yes]" >&2
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
FLAG_YES=0
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
    --yes)
      FLAG_YES=1
      shift
      ;;
    --*)
      usage
      exit 1
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

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

TOOLKIT_ROOT="$(make_absolute "$TOOLKIT_ROOT")"
OPENCLAW_HOME_DIR="$(make_absolute "$OPENCLAW_HOME_DIR")"
OPENCLAW_SCRIPTS_DIR_ABS="$(make_absolute "$OPENCLAW_SCRIPTS_DIR_RAW")"

TARGET="$TOOLKIT_ROOT/skills"
LINK="$OPENCLAW_HOME_DIR/skills"
SCRIPTS_TARGET="$TOOLKIT_ROOT/scripts"
SCRIPTS_LINK="$OPENCLAW_SCRIPTS_DIR_ABS"

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

attempt_link() {
  local link=$1
  local target=$2

  if [ ! -d "$target" ]; then
    echo "ERROR: $target is missing or not a directory. Ensure your toolkit checkout includes the required tree, or fix your toolkit root." >&2
    LINK_FAILED=1
    return
  fi

  if [ -L "$link" ]; then
    local CURRENT_CANON TARGET_CANON
    CURRENT_CANON="$(resolve_path "$link" || true)"
    TARGET_CANON="$(resolve_path "$target" || true)"
    if [ -n "$CURRENT_CANON" ] && [ -n "$TARGET_CANON" ] && [ "$CURRENT_CANON" = "$TARGET_CANON" ]; then
      echo "Already linked: $link → $target"
      return
    fi
    echo "Warning: $link currently points to $(readlink "$link")"
    if [ "$FLAG_YES" -eq 1 ]; then
      if ! rm "$link"; then
        LINK_FAILED=1
        return
      fi
    else
      read -r -p "Overwrite? [y/N] " answer
      if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
        if ! rm "$link"; then
          LINK_FAILED=1
          return
        fi
      else
        LINK_FAILED=1
        return
      fi
    fi
  fi

  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "ERROR: $link exists as a real directory/file. Remove or rename it manually, then re-run this script." >&2
    LINK_FAILED=1
    return
  fi

  if [ ! -e "$link" ]; then
    if ! mkdir -p "$(dirname "$link")"; then
      LINK_FAILED=1
      return
    fi
    if ! ln -s "$target" "$link"; then
      LINK_FAILED=1
      return
    fi
  fi

  echo "Linked: $link → $(readlink "$link")"
}

TOOLKIT="$TOOLKIT_ROOT"
if [ -L "$TOOLKIT" ] || [ -e "$TOOLKIT" ]; then
  if [ ! -d "$TOOLKIT" ]; then
    echo "ERROR: $TOOLKIT exists but is not a valid directory (toolkit root must be a directory). Remove or replace it, then: ln -s /path/to/repo $TOOLKIT"
    exit 1
  fi
else
  echo "ERROR: $TOOLKIT does not exist or does not resolve. Create it first: ln -s /path/to/repo $TOOLKIT"
  exit 1
fi

if [ "$LINK" = "$SCRIPTS_LINK" ]; then
  echo "ERROR: skills link path and scripts link path are identical ($LINK). Provide --openclaw-scripts-dir to set a distinct path." >&2
  exit 1
fi

LINK_FAILED=0
attempt_link "$LINK" "$TARGET"
attempt_link "$SCRIPTS_LINK" "$SCRIPTS_TARGET"

if [ "$LINK_FAILED" -ne 0 ]; then
  exit 1
fi
exit 0
