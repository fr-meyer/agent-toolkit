#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
skill_dir="$(cd -- "$script_dir/.." && pwd)"
script="$skill_dir/scripts/container-runtime-preflight.sh"

tmp="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

mkdir -p "$tmp/bin"

cat > "$tmp/bin/fake-service" <<'EOF'
#!/usr/bin/env bash
echo "fake-service 2.4.1"
EOF

cat > "$tmp/bin/docker" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "inspect" ]; then
  echo "registry.example.test/fake-service:2.4.1|sha256:test"
fi
EOF

chmod +x "$tmp/bin/fake-service" "$tmp/bin/docker"

safe_env="$tmp/safe.env"
old_env="$tmp/old.env"
printf '%s\n' 'SERVICE_IMAGE=registry.example.test/fake-service:2.4.1' > "$safe_env"
printf '%s\n' 'SERVICE_IMAGE=registry.example.test/fake-service:2.3.0' > "$old_env"

run_preflight() {
  PATH="$tmp/bin:$PATH" "$script" "$@"
}

safe_output="$(
  run_preflight \
    --live-version-command 'fake-service --version' \
    --deployment-env "$safe_env" \
    --image-var SERVICE_IMAGE \
    --container fake-service \
    --operation restart \
    --target-version 2.4.1 \
    --strict
)"
grep -q '^preflight_status=safe-to-proceed$' <<<"$safe_output"

set +e
drift_output="$(
  run_preflight \
    --live-version-command 'fake-service --version' \
    --deployment-env "$old_env" \
    --image-var SERVICE_IMAGE \
    --container fake-service \
    --operation restart \
    --target-version 2.4.1 \
    --strict
)"
drift_status=$?
set -e
test "$drift_status" -ne 0
grep -q '^preflight_status=version-drift-blocker$' <<<"$drift_output"

set +e
upgrade_output="$(
  run_preflight \
    --live-version-command 'fake-service --version' \
    --deployment-env "$old_env" \
    --image-var SERVICE_IMAGE \
    --container fake-service \
    --operation upgrade \
    --target-version 2.4.1 \
    --strict
)"
upgrade_status=$?
set -e
test "$upgrade_status" -ne 0
grep -q '^preflight_status=needs-image-update$' <<<"$upgrade_output"

echo "container-runtime-preflight regression tests passed"
