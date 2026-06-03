#!/usr/bin/env bash
set -u

usage() {
  cat <<'USAGE'
Usage: openclaw-runtime-preflight.sh [options]

Read-only OpenClaw runtime change preflight. It compares the live OpenClaw
version, Compose image tag, and running container image before restart,
recreate, rebuild, upgrade, or repair work.

Options:
  --compose-env PATH        Host Compose .env file containing OPENCLAW_IMAGE.
  --image-var NAME          Image variable name in .env (default: OPENCLAW_IMAGE).
  --container NAME          Docker container name or ID to inspect.
  --target-version VERSION  Intended OpenClaw version.
  --operation NAME          inspect, restart, recreate, rebuild, upgrade, repair, rollback.
                            Default: inspect.
  --phase NAME              pre-change or post-change. Default: pre-change.
  --strict                  Exit non-zero when blockers are found.
  -h, --help                Show this help.

This script never sources dotenv files and never prints secret values.
USAGE
}

compose_env=""
image_var="OPENCLAW_IMAGE"
container=""
target_version=""
operation="inspect"
phase="pre-change"
strict=0
target_compose_mismatch=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --compose-env)
      if [ "$#" -lt 2 ]; then
        echo "ERROR: --compose-env requires a value" >&2
        exit 2
      fi
      compose_env="${2:-}"
      shift 2
      ;;
    --image-var)
      if [ "$#" -lt 2 ]; then
        echo "ERROR: --image-var requires a value" >&2
        exit 2
      fi
      image_var="${2:-}"
      shift 2
      ;;
    --container)
      if [ "$#" -lt 2 ]; then
        echo "ERROR: --container requires a value" >&2
        exit 2
      fi
      container="${2:-}"
      shift 2
      ;;
    --target-version)
      if [ "$#" -lt 2 ]; then
        echo "ERROR: --target-version requires a value" >&2
        exit 2
      fi
      target_version="${2:-}"
      shift 2
      ;;
    --operation)
      if [ "$#" -lt 2 ]; then
        echo "ERROR: --operation requires a value" >&2
        exit 2
      fi
      operation="${2:-}"
      shift 2
      ;;
    --phase)
      if [ "$#" -lt 2 ]; then
        echo "ERROR: --phase requires a value" >&2
        exit 2
      fi
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
  printf '%s\n' "$1" | grep -Eo '20[0-9]{2}\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?' | tail -n 1 || true
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
if command -v openclaw >/dev/null 2>&1; then
  live_output="$(openclaw --version 2>&1 || true)"
  live_version="$(extract_version "$live_output")"
else
  add_warning "openclaw command not found in PATH."
fi

compose_image=""
compose_version=""
if [ -n "$compose_env" ]; then
  if [ -f "$compose_env" ]; then
    compose_image="$(read_dotenv_value "$compose_env" "$image_var" || true)"
    if [ -n "$compose_image" ]; then
      compose_version="$(extract_version "$compose_image")"
    else
      add_warning "$image_var not found in $compose_env."
    fi
  else
    add_warning "Compose env file not found: $compose_env."
  fi
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
    else
      add_warning "Docker could not inspect container: $container."
    fi
  else
    add_warning "docker command not found in PATH."
  fi
fi

printf 'OpenClaw runtime preflight\n'
printf 'operation=%s\n' "$operation"
printf 'phase=%s\n' "$phase"
printf 'strict=%s\n' "$strict"
printf 'target_version=%s\n' "${target_version:-unknown}"
printf 'live_version=%s\n' "${live_version:-unknown}"
printf 'compose_env=%s\n' "${compose_env:-not-provided}"
printf 'image_var=%s\n' "$image_var"
printf 'compose_image=%s\n' "${compose_image:-unknown}"
printf 'compose_image_version=%s\n' "${compose_version:-unknown}"
printf 'container=%s\n' "${container:-not-provided}"
printf 'running_image_ref=%s\n' "${running_image_ref:-unknown}"
printf 'running_image_version=%s\n' "${running_image_version:-unknown}"
printf 'running_image_id=%s\n' "${running_image_id:-unknown}"

if [ -z "$live_version" ] && [ "$operation" != "inspect" ]; then
  add_warning "Live OpenClaw version is unknown for a mutating operation."
fi

if [ -n "$target_version" ]; then
  if [ -n "$compose_version" ] && [ "$compose_version" != "$target_version" ]; then
    target_compose_mismatch=1
    add_blocker "Compose image version ($compose_version) does not match target version ($target_version)."
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
    if [ -n "$live_version" ] && [ -n "$compose_version" ] && [ "$live_version" != "$compose_version" ]; then
      add_blocker "Live version ($live_version) differs from Compose image version ($compose_version); recreate/rebuild could roll forward/back unexpectedly."
    fi
    ;;
  upgrade)
    if [ -z "$target_version" ]; then
      add_blocker "Upgrade operation requires --target-version."
    fi
    ;;
  rollback)
    if [ -z "$target_version" ]; then
      add_warning "Rollback target version not provided; make the rollback image/snapshot explicit before mutation."
    fi
    ;;
esac

if [ -n "$compose_version" ] && [ -n "$running_image_version" ] && [ "$compose_version" != "$running_image_version" ]; then
  add_warning "Running container image version ($running_image_version) differs from Compose image version ($compose_version). A recreate will change the runtime image."
fi

if [ -z "$compose_env" ] && [ "$operation" != "inspect" ]; then
  add_warning "No Compose env file was provided for a mutating operation."
fi

if [ -z "$container" ] && [ "$operation" != "inspect" ]; then
  add_warning "No container was provided for a mutating operation."
fi

status="safe-to-proceed"
if [ "$operation" = "inspect" ]; then
  status="read-only-only"
elif [ "$operation" = "upgrade" ] && [ "$target_compose_mismatch" -eq 1 ]; then
  status="needs-image-update"
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
