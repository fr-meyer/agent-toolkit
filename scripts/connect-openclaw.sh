#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TOOLKIT="$HOME/.agent-toolkit"
if [ -L "$TOOLKIT" ] || [ -e "$TOOLKIT" ]; then
  if [ ! -d "$TOOLKIT" ]; then
    echo "ERROR: ~/.agent-toolkit exists but is not a valid directory (toolkit root must be a directory). Remove or replace it, then: ln -s /path/to/repo ~/.agent-toolkit"
    exit 1
  fi
else
  echo "ERROR: ~/.agent-toolkit does not exist or does not resolve. Create it first: ln -s /path/to/repo ~/.agent-toolkit"
  exit 1
fi

TARGET="$HOME/.agent-toolkit/skills"
if [ ! -d "$TARGET" ]; then
  echo "ERROR: ~/.agent-toolkit/skills is missing or not a directory. Ensure your toolkit checkout includes the skills tree, or fix ~/.agent-toolkit to point at the repository root."
  exit 1
fi
LINK="$HOME/.openclaw/skills"

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
  mkdir -p "$(dirname "$LINK")"
  ln -s "$TARGET" "$LINK"
fi

echo "Linked: $LINK → $(readlink "$LINK")"
