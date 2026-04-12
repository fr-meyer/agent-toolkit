#!/usr/bin/env bash
set -euo pipefail

RUNTIME="${1:-${AGENT_RUNTIME:-none}}"
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
  local fallback="$2"
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
  if command -v "$fallback" >/dev/null 2>&1; then
    command -v "$fallback"
    return 0
  fi
  return 1
}

find_cursor_agent_binary() {
  local configured="${CURSOR_CLI:-}"
  local candidate
  if candidate=$(resolve_binary "$configured" agent 2>/dev/null); then
    printf '%s\n' "$candidate"
    return 0
  fi
  for candidate in \
    "$HOME/.local/bin/agent" \
    "$HOME/.cursor/bin/agent" \
    "$HOME/bin/agent" \
    "/usr/local/bin/agent" \
    "/opt/homebrew/bin/agent"
  do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

write_status() {
  local status="$1"
  local runtime="$2"
  local binary="$3"
  local version="$4"
  local auth_mode="$5"
  local note="$6"
  if [[ -z "$OUT_DIR" ]]; then
    return 0
  fi
  mkdir -p "$OUT_DIR"
  STATUS="$status" RUNTIME_NAME="$runtime" BINARY_PATH="$binary" VERSION_TEXT="$version" AUTH_MODE="$auth_mode" NOTE_TEXT="$note" OUT_PATH="$OUT_DIR/agent-runtime-setup.json" \
    python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

payload = {
    'status': os.environ['STATUS'],
    'runtime': os.environ['RUNTIME_NAME'],
    'binary': os.environ['BINARY_PATH'] or None,
    'version': os.environ['VERSION_TEXT'] or None,
    'authMode': os.environ['AUTH_MODE'] or None,
    'note': os.environ['NOTE_TEXT'] or None,
    'metadata': {
        'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'source': 'setup_agent_runtime.sh',
    },
}
Path(os.environ['OUT_PATH']).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
PY
}

case "$RUNTIME" in
  none)
    write_status "skipped" "$RUNTIME" "" "" "" "No agent runtime requested."
    exit 0
    ;;
  custom)
    write_status "skipped" "$RUNTIME" "" "" "external" "Custom runtime selected. Workflow did not install an agent runtime automatically."
    exit 0
    ;;
  cursor)
    append_path "$HOME/.local/bin"
    append_path "$HOME/.cursor/bin"
    append_path "$HOME/bin"

    CURSOR_AGENT_BIN="$(find_cursor_agent_binary || true)"
    if [[ -z "$CURSOR_AGENT_BIN" ]]; then
      echo "Installing Cursor CLI via the official installer..."
      bash -lc 'curl https://cursor.com/install -fsS | bash'
      append_path "$HOME/.local/bin"
      append_path "$HOME/.cursor/bin"
      append_path "$HOME/bin"
      CURSOR_AGENT_BIN="$(find_cursor_agent_binary || true)"
    fi

    if [[ -z "$CURSOR_AGENT_BIN" ]]; then
      note="Cursor CLI installation completed, but no 'agent' binary was found in the expected locations. Set cursor_cli to an explicit binary path if needed."
      write_status "failed" "$RUNTIME" "" "" "environment_api_key" "$note"
      echo "$note" >&2
      exit 1
    fi

    if [[ -z "${CURSOR_API_KEY:-}" ]]; then
      note="CURSOR_API_KEY is required when agent_runtime=cursor so the downstream agent command can run headlessly."
      write_status "failed" "$RUNTIME" "$CURSOR_AGENT_BIN" "$($CURSOR_AGENT_BIN --version 2>/dev/null | head -n 1 || true)" "environment_api_key" "$note"
      echo "$note" >&2
      exit 1
    fi

    VERSION_TEXT="$($CURSOR_AGENT_BIN --version 2>/dev/null | head -n 1 || true)"
    note="Cursor agent CLI is available. CURSOR_API_KEY has been provided to the job environment for downstream headless agent commands."
    write_status "ready" "$RUNTIME" "$CURSOR_AGENT_BIN" "$VERSION_TEXT" "environment_api_key" "$note"
    echo "Cursor agent CLI ready: $CURSOR_AGENT_BIN"
    if [[ -n "$VERSION_TEXT" ]]; then
      echo "$VERSION_TEXT"
    fi
    ;;
  *)
    note="Unsupported agent runtime: $RUNTIME"
    write_status "failed" "$RUNTIME" "" "" "" "$note"
    echo "$note" >&2
    exit 1
    ;;
esac
