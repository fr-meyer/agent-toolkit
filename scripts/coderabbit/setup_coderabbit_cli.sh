#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${CODERABBIT_OUT_DIR:-}"

append_path() {
  local dir="$1"
  if [[ -z "$dir" || ! -d "$dir" ]]; then
    return 0
  fi
  case ":$PATH:" in
    *":$dir:"*) ;;
    *) export PATH="$dir:$PATH" ;;
  esac
  if [[ -n "${GITHUB_PATH:-}" ]]; then
    printf '%s\n' "$dir" >> "$GITHUB_PATH"
  fi
}

resolve_binary() {
  local configured="${1:-}"
  if [[ -n "$configured" ]]; then
    if [[ -x "$configured" ]]; then
      printf '%s\n' "$configured"
      return 0
    fi
    if command -v "$configured" >/dev/null 2>&1; then
      command -v "$configured"
      return 0
    fi
  fi
  local candidate
  for candidate in coderabbit cr; do
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

write_status() {
  local status="$1"
  local binary="$2"
  local version="$3"
  local note="$4"
  if [[ -z "$OUT_DIR" ]]; then
    return 0
  fi
  mkdir -p "$OUT_DIR"
  STATUS="$status" BINARY_PATH="$binary" VERSION_TEXT="$version" NOTE_TEXT="$note" OUT_PATH="$OUT_DIR/coderabbit-cli-setup.json" \
    python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

payload = {
    'status': os.environ['STATUS'],
    'binary': os.environ['BINARY_PATH'] or None,
    'version': os.environ['VERSION_TEXT'] or None,
    'note': os.environ['NOTE_TEXT'] or None,
    'metadata': {
        'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'source': 'setup_coderabbit_cli.sh',
    },
}
Path(os.environ['OUT_PATH']).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
PY
}

append_path "$HOME/.local/bin"
append_path "$HOME/bin"

if [[ -z "${CODERABBIT_API_KEY:-}" ]]; then
  note="CODERABBIT_API_KEY is required when validation is enabled."
  write_status "failed" "" "" "$note"
  echo "$note" >&2
  exit 1
fi

CR_BIN="$(resolve_binary "${CODERABBIT_CLI:-}" || true)"
if [[ -z "$CR_BIN" ]]; then
  echo "Installing CodeRabbit CLI via the official installer..."
  bash -lc 'curl -fsSL https://cli.coderabbit.ai/install.sh | sh'
  append_path "$HOME/.local/bin"
  append_path "$HOME/bin"
  CR_BIN="$(resolve_binary "${CODERABBIT_CLI:-}" || true)"
fi

if [[ -z "$CR_BIN" ]]; then
  note="CodeRabbit CLI installation completed, but no 'coderabbit' or 'cr' binary was found. Set coderabbit_cli to an explicit binary path if needed."
  write_status "failed" "" "" "$note"
  echo "$note" >&2
  exit 1
fi

echo "Authenticating CodeRabbit CLI..."
"$CR_BIN" auth login --api-key "$CODERABBIT_API_KEY"

VERSION_TEXT="$($CR_BIN --version 2>/dev/null | head -n 1 || true)"
note="CodeRabbit CLI is installed and authenticated for downstream validation."
write_status "ready" "$CR_BIN" "$VERSION_TEXT" "$note"
echo "CodeRabbit CLI ready: $CR_BIN"
if [[ -n "$VERSION_TEXT" ]]; then
  echo "$VERSION_TEXT"
fi
