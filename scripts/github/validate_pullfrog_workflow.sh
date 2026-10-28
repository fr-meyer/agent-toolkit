#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
actionlint_version="1.7.12"
# actionlint uses Go's `amd64` release-asset suffix for Linux x86-64 builds.
# Keep the asset name and checksum aligned with the upstream versioned checksum manifest.
actionlint_sha256="8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"
archive_name="actionlint_${actionlint_version}_linux_amd64.tar.gz"
download_url="https://github.com/rhysd/actionlint/releases/download/v${actionlint_version}/${archive_name}"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

curl \
  --fail \
  --silent \
  --show-error \
  --location \
  --proto '=https' \
  --tlsv1.2 \
  --output "$tmp_dir/$archive_name" \
  "$download_url"

printf '%s  %s\n' "$actionlint_sha256" "$tmp_dir/$archive_name" | sha256sum --check --status
tar -xzf "$tmp_dir/$archive_name" -C "$tmp_dir" actionlint

"$tmp_dir/actionlint" \
  "$repo_root/templates/starter-workflows/pullfrog.yml" \
  "$repo_root/.github/workflows/pullfrog.yml" \
  "$repo_root/templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml" \
  "$repo_root/.github/workflows/pullfrog-cloud-coordinator-dry-run.yml" \
  "$repo_root/templates/starter-workflows/pullfrog-cloud-remediation-loop.yml" \
  "$repo_root/.github/workflows/pullfrog-cloud-remediation-loop.yml"

python3 -m unittest discover \
  -s "$repo_root/scripts/github/tests" \
  -p 'test_pullfrog_*workflow_policy.py' \
  -v
