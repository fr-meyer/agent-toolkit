#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  echo "Usage: ${0##*/} [--toolkit-root <path>] [--openclaw-home <path>] [--yes]" >&2
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

make_absolute() {
  case "$1" in
    /*)
      printf '%s\n' "$1"
      ;;
    '~')
      printf '%s\n' "$HOME"
      ;;
    '~/'*)
      printf '%s\n' "${HOME}/${1#~/}"
      ;;
    *)
      printf '%s\n' "${PWD}/$1"
      ;;
  esac
}

TOOLKIT_ROOT="$(make_absolute "$TOOLKIT_ROOT")"
OPENCLAW_HOME_DIR="$(make_absolute "$OPENCLAW_HOME_DIR")"

TARGET="$TOOLKIT_ROOT/skills"
LINK="$OPENCLAW_HOME_DIR/skills"

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

if [ ! -d "$TARGET" ]; then
  echo "ERROR: $TARGET is missing or not a directory. Ensure your toolkit checkout includes the skills tree, or fix $TOOLKIT to point at the repository root."
  exit 1
fi

if [ -L "$LINK" ]; then
  CURRENT_CANON="$(resolve_path "$LINK" || true)"
  TARGET_CANON="$(resolve_path "$TARGET" || true)"
  if [ -n "$CURRENT_CANON" ] && [ -n "$TARGET_CANON" ] && [ "$CURRENT_CANON" = "$TARGET_CANON" ]; then
    echo "Already linked: $LINK → $TARGET"
    exit 0
  fi
  echo "Warning: $LINK currently points to $(readlink "$LINK")"
  if [ "$FLAG_YES" -eq 1 ]; then
    rm "$LINK"
  else
    read -r -p "Overwrite? [y/N] " answer
    if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
      rm "$LINK"
    else
      exit 1
    fi
  fi
fi

if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "ERROR: $LINK exists as a real directory/file. Remove or rename it manually, then re-run this script."
  exit 1
fi

if [ ! -e "$LINK" ]; then
  mkdir -p "$(dirname "$LINK")"
  ln -s "$TARGET" "$LINK"
fi

echo "Linked: $LINK → $(readlink "$LINK")"
