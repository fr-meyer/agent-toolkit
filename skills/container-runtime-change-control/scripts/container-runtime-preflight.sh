#!/usr/bin/env bash
set -u

usage() {
  cat <<'USAGE'
Usage: container-runtime-preflight.sh [options]

Read-only container runtime change preflight. It compares a live service
version, durable deployment image/spec, and running container image before
restart, recreate, rebuild, upgrade, rollback, or repair work.

Options:
  --live-version-command CMD  Command that prints the live service version.
                              Run with "sh -c"; quote it carefully.
  --deployment-image REF      Durable deployment image reference to compare.
  --deployment-env PATH       Dotenv file containing an image variable.
  --image-var NAME            Image variable name in --deployment-env.
  --container NAME            Docker container name or ID to inspect.
  --target-version VERSION    Intended service/software version.
  --rollback-artifact DESC    Existing rollback artifact or backup plan evidence:
                              image tag, image archive, registry copy, snapshot,
                              or env/manifest backup. Do not include secrets.
                              Values such as "unavailable" fail closed.
  --operation NAME            inspect, restart, recreate, rebuild, upgrade,
                              repair, rollback. Default: inspect.
  --phase NAME                pre-change or post-change. Default: pre-change.
  --strict                    Exit non-zero when not safe-to-proceed.
  -h, --help                  Show this help.

This script never sources dotenv files. It prints supplied image and rollback
evidence, so do not pass tokens, signed URLs, or secret-bearing references.
USAGE
}

live_version_command=""
deployment_image=""
deployment_env=""
image_var=""
container=""
target_version=""
rollback_artifact=""
operation="inspect"
phase="pre-change"
strict=0
target_deployment_mismatch=0

require_value() {
  flag="$1"
  if [ "$#" -lt 2 ] || [ -z "${2:-}" ]; then
    echo "ERROR: $flag requires a value" >&2
    exit 2
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --live-version-command)
      require_value "$@"
      live_version_command="${2:-}"
      shift 2
      ;;
    --deployment-image)
      require_value "$@"
      deployment_image="${2:-}"
      shift 2
      ;;
    --deployment-env|--compose-env)
      require_value "$@"
      deployment_env="${2:-}"
      shift 2
      ;;
    --image-var)
      require_value "$@"
      image_var="${2:-}"
      shift 2
      ;;
    --container)
      require_value "$@"
      container="${2:-}"
      shift 2
      ;;
    --target-version)
      require_value "$@"
      target_version="${2:-}"
      shift 2
      ;;
    --rollback-artifact)
      require_value "$@"
      rollback_artifact="${2:-}"
      shift 2
      ;;
    --operation)
      require_value "$@"
      operation="${2:-}"
      shift 2
      ;;
    --phase)
      require_value "$@"
      phase="${2:-}"
      shift 2
      ;;
    --strict)
      strict=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$operation" in
  inspect|restart|recreate|rebuild|upgrade|repair|rollback) ;;
  *)
    echo "ERROR: unsupported --operation: $operation" >&2
    exit 2
    ;;
esac

case "$phase" in
  pre-change|post-change) ;;
  *)
    echo "ERROR: unsupported --phase: $phase" >&2
    exit 2
    ;;
esac

extract_version() {
  printf '%s\n' "$1" \
    | grep -Eo 'v?[0-9]+([.][0-9]+){1,3}([-+][A-Za-z0-9._-]+)?' \
    | sed 's/^v//' \
    | tail -n 1 || true
}

read_dotenv_value() {
  file="$1"
  key="$2"
  [ -f "$file" ] || return 1
  awk -v key="$key" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      line = $0
      sub(/^[[:space:]]*export[[:space:]]+/, "", line)
      if (line ~ "^[[:space:]]*" key "[[:space:]]*=") {
        sub("^[[:space:]]*" key "[[:space:]]*=[[:space:]]*", "", line)
        sub(/[[:space:]]+#.*$/, "", line)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
        if (line ~ /^".*"$/ || line ~ /^'\''.*'\''$/) {
          line = substr(line, 2, length(line) - 2)
        }
        print line
        exit
      }
    }
  ' "$file"
}

blockers=0
warnings=0

add_blocker() {
  blockers=$((blockers + 1))
  printf 'BLOCKER: %s\n' "$1"
}

add_warning() {
  warnings=$((warnings + 1))
  printf 'WARNING: %s\n' "$1"
}

live_output=""
live_version=""
if [ -n "$live_version_command" ]; then
  live_output="$(sh -c "$live_version_command" 2>&1 || true)"
  live_version="$(extract_version "$live_output")"
  if [ -z "$live_version" ]; then
    add_warning "Live version command ran but no version could be parsed."
  fi
elif [ "$operation" != "inspect" ]; then
  add_warning "No --live-version-command was provided for a mutating operation."
fi

env_image=""
if [ -n "$deployment_env" ]; then
  if [ -z "$image_var" ]; then
    add_warning "--deployment-env was provided without --image-var."
  elif [ -f "$deployment_env" ]; then
    env_image="$(read_dotenv_value "$deployment_env" "$image_var" || true)"
    if [ -z "$env_image" ]; then
      add_warning "$image_var not found in $deployment_env."
    fi
  else
    add_warning "Deployment env file not found: $deployment_env."
  fi
fi

if [ -z "$deployment_image" ] && [ -n "$env_image" ]; then
  deployment_image="$env_image"
fi

deployment_version=""
if [ -n "$deployment_image" ]; then
  deployment_version="$(extract_version "$deployment_image")"
  if [ -z "$deployment_version" ]; then
    add_warning "Deployment image was provided but no version could be parsed."
  fi
elif [ "$operation" != "inspect" ]; then
  add_warning "No durable deployment image/spec was provided for a mutating operation."
fi

running_image_ref=""
running_image_id=""
running_image_version=""
if [ -n "$container" ]; then
  if command -v docker >/dev/null 2>&1; then
    inspect_output="$(docker inspect --format '{{.Config.Image}}|{{.Image}}' "$container" 2>/dev/null || true)"
    if [ -n "$inspect_output" ]; then
      running_image_ref="${inspect_output%%|*}"
      running_image_id="${inspect_output#*|}"
      running_image_version="$(extract_version "$running_image_ref")"
      if [ -z "$running_image_version" ]; then
        add_warning "Running container image was inspected but no version could be parsed."
      fi
    else
      add_warning "Docker could not inspect container: $container."
    fi
  else
    add_warning "docker command not found in PATH."
  fi
elif [ "$operation" != "inspect" ]; then
  add_warning "No --container was provided for a mutating operation."
fi

printf 'Container runtime preflight\n'
printf 'operation=%s\n' "$operation"
printf 'phase=%s\n' "$phase"
printf 'strict=%s\n' "$strict"
printf 'target_version=%s\n' "${target_version:-unknown}"
printf 'live_version_command=%s\n' "${live_version_command:-not-provided}"
printf 'live_version=%s\n' "${live_version:-unknown}"
printf 'deployment_env=%s\n' "${deployment_env:-not-provided}"
printf 'image_var=%s\n' "${image_var:-not-provided}"
printf 'deployment_image=%s\n' "${deployment_image:-unknown}"
printf 'deployment_image_version=%s\n' "${deployment_version:-unknown}"
printf 'container=%s\n' "${container:-not-provided}"
printf 'running_image_ref=%s\n' "${running_image_ref:-unknown}"
printf 'running_image_version=%s\n' "${running_image_version:-unknown}"
printf 'running_image_id=%s\n' "${running_image_id:-unknown}"
printf 'rollback_artifact=%s\n' "${rollback_artifact:-not-provided}"

if [ "$operation" != "inspect" ] && [ "$phase" = "pre-change" ] && [ -z "$rollback_artifact" ]; then
  add_warning "No --rollback-artifact was provided for a mutating operation. Capture or identify a known-good image tag, image archive, registry copy, snapshot, or manifest backup before mutation."
fi

if [ -n "$rollback_artifact" ]; then
  case "$(printf '%s' "$rollback_artifact" | tr '[:upper:]' '[:lower:]')" in
    *unavailable*|*not-available*|*not_available*|*"not available"*|none|n/a|na)
      add_warning "Rollback artifact was declared unavailable. Keep the operation read-only until the operator explicitly accepts that risk."
      ;;
  esac
fi

if [ -n "$target_version" ]; then
  if [ -n "$deployment_version" ] && [ "$deployment_version" != "$target_version" ]; then
    target_deployment_mismatch=1
    add_blocker "Deployment image version ($deployment_version) does not match target version ($target_version)."
  fi
  if [ "$phase" = "post-change" ] && [ -n "$live_version" ] && [ "$live_version" != "$target_version" ]; then
    add_blocker "Post-change live version ($live_version) does not match target version ($target_version)."
  fi
fi

case "$operation" in
  restart|recreate|rebuild|repair)
    if [ -n "$target_version" ] && [ -n "$live_version" ] && [ "$target_version" != "$live_version" ]; then
      add_blocker "Operation '$operation' should preserve live version, but target ($target_version) differs from live ($live_version). Use --operation upgrade or rollback if intentional."
    fi
    if [ -n "$live_version" ] && [ -n "$deployment_version" ] && [ "$live_version" != "$deployment_version" ]; then
      add_blocker "Live version ($live_version) differs from deployment image version ($deployment_version); recreate/rebuild could roll forward/back unexpectedly."
    fi
    ;;
  upgrade)
    if [ -z "$target_version" ]; then
      add_blocker "Upgrade operation requires --target-version."
    fi
    ;;
  rollback)
    if [ -z "$target_version" ]; then
      add_blocker "Rollback operation requires an explicit --target-version."
    fi
    ;;
esac

if [ -n "$deployment_version" ] && [ -n "$running_image_version" ] && [ "$deployment_version" != "$running_image_version" ]; then
  add_warning "Running container image version ($running_image_version) differs from deployment image version ($deployment_version). A recreate will change the runtime image."
fi

status="safe-to-proceed"
if [ "$operation" = "inspect" ]; then
  status="read-only-only"
elif [ "$operation" = "upgrade" ] && [ "$target_deployment_mismatch" -eq 1 ]; then
  status="needs-image-update"
elif [ "$operation" = "rollback" ]; then
  status="rollback-required"
elif [ "$blockers" -gt 0 ]; then
  status="version-drift-blocker"
elif [ "$warnings" -gt 0 ]; then
  status="read-only-only"
fi

printf 'preflight_status=%s\n' "$status"
printf 'warnings=%s\n' "$warnings"
printf 'blockers=%s\n' "$blockers"

if [ "$strict" -eq 1 ] && [ "$status" != "safe-to-proceed" ]; then
  exit 1
fi

exit 0
