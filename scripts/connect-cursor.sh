#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TOOLKIT="$HOME/.agent-toolkit"
if [ ! -e "$TOOLKIT" ]; then
  echo "ERROR: ~/.agent-toolkit does not exist or does not resolve. Create it first: ln -s /path/to/repo ~/.agent-toolkit"
  exit 1
fi

GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || GIT_ROOT=""
if [ -z "$GIT_ROOT" ]; then
  echo "Warning: this doesn't look like a project directory."
  read -r -p "Proceed anyway? [y/N] " answer
  if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
    exit 1
  fi
fi

TARGET="$HOME/.agent-toolkit/cursor/rules"
LINK=".cursor/rules"

if [ -L "$LINK" ]; then
  CURRENT_TARGET="$(readlink "$LINK")"
  if [ "$CURRENT_TARGET" = "$TARGET" ]; then
    echo "Already linked: $LINK → $TARGET"
    exit 0
  fi
  echo "Warning: $LINK currently points to $CURRENT_TARGET"
  read -r -p "Overwrite? [y/N] " answer
  if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
    rm "$LINK"
  else
    exit 1
  fi
fi

if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "ERROR: $LINK exists as a real directory/file. Remove or rename it manually, then re-run this script."
  exit 1
fi

if [ ! -e "$LINK" ]; then
  mkdir -p .cursor
  ln -s "$TARGET" "$LINK"
fi

echo "Linked: $LINK → $(readlink "$LINK")"
