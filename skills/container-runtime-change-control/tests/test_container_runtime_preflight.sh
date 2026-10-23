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
case "${1:-}" in
  --failed-stdout)
    echo "fake-service 2.4.1"
    exit 7
    ;;
  --failed-stderr)
    echo "private-diagnostic-marker: fake-service 2.4.1 unavailable" >&2
    exit 9
    ;;
  --failed-empty)
    exit 5
    ;;
esac
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
    --rollback-artifact 'image-tag=fake-service:backup-test' \
    --strict
)"
grep -q '^preflight_status=safe-to-proceed$' <<<"$safe_output"
grep -q '^rollback_artifact=image-tag=fake-service:backup-test$' <<<"$safe_output"

# A failed probe cannot authorize mutation even when its stdout or stderr
# contains exactly the version printed by the deployment and running image.
for failure_mode in failed-stdout failed-stderr failed-empty; do
  for guarded_operation in restart recreate rebuild repair upgrade; do
    set +e
    failed_probe_output="$(
      run_preflight \
        --live-version-command "fake-service --$failure_mode" \
        --deployment-env "$safe_env" \
        --image-var SERVICE_IMAGE \
        --container fake-service \
        --operation "$guarded_operation" \
        --target-version 2.4.1 \
        --rollback-artifact 'image-tag=fake-service:backup-test' \
        --strict
    )"
    failed_probe_status=$?
    set -e
    test "$failed_probe_status" -ne 0
    grep -q '^preflight_status=read-only-only$' <<<"$failed_probe_output"
    grep -q '^live_version=unknown$' <<<"$failed_probe_output"
    grep -q 'Live version command failed (exit ' <<<"$failed_probe_output"
    if grep -q 'private-diagnostic-marker' <<<"$failed_probe_output"; then
      echo "Failed probe diagnostics leaked into preflight output" >&2
      exit 1
    fi
  done
done

# Non-strict mode may return diagnostics successfully, but must still report
# read-only-only and discard the failed probe's parseable version.
diagnostic_output="$(
  run_preflight \
    --live-version-command 'fake-service --failed-stdout' \
    --deployment-env "$safe_env" \
    --image-var SERVICE_IMAGE \
    --container fake-service \
    --operation rebuild \
    --target-version 2.4.1 \
    --rollback-artifact 'image-tag=fake-service:backup-test'
)"
grep -q '^preflight_status=read-only-only$' <<<"$diagnostic_output"
grep -q '^live_version=unknown$' <<<"$diagnostic_output"

set +e
missing_backup_output="$(
  run_preflight \
    --live-version-command 'fake-service --version' \
    --deployment-env "$safe_env" \
    --image-var SERVICE_IMAGE \
    --container fake-service \
    --operation restart \
    --target-version 2.4.1 \
    --strict
)"
missing_backup_status=$?
set -e
test "$missing_backup_status" -ne 0
grep -q '^preflight_status=read-only-only$' <<<"$missing_backup_output"
grep -q 'No --rollback-artifact was provided' <<<"$missing_backup_output"

set +e
unavailable_backup_output="$(
  run_preflight \
    --live-version-command 'fake-service --version' \
    --deployment-env "$safe_env" \
    --image-var SERVICE_IMAGE \
    --container fake-service \
    --operation restart \
    --target-version 2.4.1 \
    --rollback-artifact unavailable \
    --strict
)"
unavailable_backup_status=$?
set -e
test "$unavailable_backup_status" -ne 0
grep -q '^preflight_status=read-only-only$' <<<"$unavailable_backup_output"
grep -q 'Rollback artifact was declared unavailable' <<<"$unavailable_backup_output"

set +e
drift_output="$(
  run_preflight \
    --live-version-command 'fake-service --version' \
    --deployment-env "$old_env" \
    --image-var SERVICE_IMAGE \
    --container fake-service \
    --operation restart \
    --target-version 2.4.1 \
    --rollback-artifact 'image-tag=fake-service:backup-test' \
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
    --rollback-artifact 'image-tag=fake-service:backup-test' \
    --strict
)"
upgrade_status=$?
set -e
test "$upgrade_status" -ne 0
grep -q '^preflight_status=needs-image-update$' <<<"$upgrade_output"

echo "container-runtime-preflight regression tests passed"
