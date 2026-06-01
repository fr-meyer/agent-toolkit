#!/usr/bin/env sh
set -eu

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [ ! -d .githooks ]; then
  echo "Missing .githooks directory at $repo_root" >&2
  exit 1
fi

chmod +x .githooks/pre-commit .githooks/pre-push
git config core.hooksPath .githooks

echo "Configured local Git hooks for $repo_root"
echo "core.hooksPath=$(git config --get core.hooksPath)"
