#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
python3 "$SCRIPT_DIR/run_commit_pass_core.py" "$@"
