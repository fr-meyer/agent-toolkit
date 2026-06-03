---
name: openclaw-runtime-change-control
description: Use this skill before changing, restarting, rebuilding, upgrading, or repairing an OpenClaw runtime. Apply it to Gateway restarts, Docker Compose operations, OpenClaw version upgrades, plugin installs, model-routing changes, wrapper/tool deployments, and recovery work where live runtime version, image tag, persistent config, and rollback state must be reconciled before mutation.
---

# OpenClaw Runtime Change Control

## Goal

Prevent accidental OpenClaw rollbacks, version drift, and unsafe runtime repairs. Treat OpenClaw runtime work as change-controlled operations, not casual shell maintenance.

Use this skill before any OpenClaw action that may affect the live service, container lifecycle, installed runtime, plugins, model routing, Gateway process, cron/runtime jobs, node bridges, wrapper scripts, Docker overlays, or deployment image.

## Hard Rules

- Start read-only. Do not restart, recreate, rebuild, install, patch config, or kill processes until preflight evidence is collected.
- Reconcile all three deployment truths before mutation:
  - live runtime version, usually `openclaw --version`;
  - durable deployment image, usually host Compose `OPENCLAW_IMAGE`;
  - actual running container image/tag/digest when Docker is available.
- If live version and recreated image version disagree, stop before any container recreate/rebuild and report the mismatch.
- Do not treat package installs inside a running container as durable deployment state unless the image is rebuilt or the hotfix is explicitly temporary.
- Do not use ad-hoc in-container Gateway kills such as `pkill -f "openclaw gateway run"` as a normal production restart path.
- Do not claim a model or runtime switch happened unless a live status tool confirms it.
- Preserve user/parallel-agent work and runtime config. Never use reset/revert/destructive cleanup as a shortcut.

## Default Workflow

### 1. Declare Intent

State the proposed operation before writing anything:

- operation type: inspect, restart, recreate, rebuild, upgrade, plugin change, model-routing change, repair, or rollback;
- intended OpenClaw version, or explicit statement that the current version should be preserved;
- affected components;
- expected host/Compose location if known;
- rollback path, such as previous image tag, env backup, VM snapshot, or explicit `rollback unavailable`.

If the target version or host deployment root is unknown and the operation can recreate a container, ask or inspect local trusted notes before proceeding.

### 2. Run Preflight

Collect evidence read-only. Prefer the bundled helper when available:

```bash
<skill-dir>/scripts/openclaw-runtime-preflight.sh \
  --compose-env /path/to/openclaw/.env \
  --container openclaw-gateway \
  --operation recreate \
  --target-version 2026.6.1-beta.2 \
  --strict
```

Use `--operation restart` when preserving the current runtime, `--operation upgrade` when moving to a new version, and `--operation inspect` for non-mutating audits.

If the helper is unavailable, gather equivalent facts manually:

```bash
openclaw --version
grep -E '^[[:space:]]*OPENCLAW_IMAGE[[:space:]]*=' /path/to/openclaw/.env
docker inspect --format '{{.Config.Image}} {{.Image}}' openclaw-gateway
openclaw models status
openclaw doctor
```

Adapt commands to the host's actual service/container names and OpenClaw version.

### 3. Classify the State

Use one primary status:

- `safe-to-proceed`: target version, durable image, and running/live state are reconciled for the requested operation.
- `needs-image-update`: live/runtime target is known but the Compose image does not yet carry the intended version.
- `version-drift-blocker`: live version, Compose image, or running image disagree in a way that a restart/recreate could change versions unexpectedly.
- `read-only-only`: required evidence is missing, Docker/Compose is inaccessible, or the operation is only an audit.
- `rollback-required`: the intended action is recovery to a known prior image/snapshot and must be stated explicitly.

Stop on anything except `safe-to-proceed` unless the user explicitly changes the goal to read-only diagnosis or an explicit rollback.

### 4. Execute the Smallest Approved Change

Prefer host-level, durable deployment paths:

- update the image tag or overlay intentionally;
- use host Docker Compose, not in-container process surgery;
- keep config/env backups before mutation;
- install plugins or wrappers through the documented OpenClaw path for the active version;
- keep model default/fallback changes separate from image/runtime changes when practical.

For risky operations, make one change at a time and verify before continuing.

### 5. Post-Change Verification

After any mutation, verify:

```bash
openclaw --version
docker inspect --format '{{.Config.Image}} {{.Image}}' <container>
openclaw doctor
openclaw models status
```

Also verify any touched surface:

- Gateway status/logs for restarts or repairs;
- plugin list/version for plugin changes;
- session status/current model for model-routing changes;
- cron/job status for scheduled runtime changes;
- wrapper/tool smoke test for deployed CLIs or overlays.

If post-change state differs from the intended target, stop and report. Do not stack additional repairs without a new preflight.

### 6. Record the Change

Write a compact durable note in the caller's normal operations log, often `memory/YYYY-MM-DD.md`, including:

- operation and target version;
- preflight status and key version/image evidence;
- files/configs/images changed;
- rollback path;
- post-change verification results;
- remaining warnings or follow-up actions.

Do not store secrets, raw tokens, signed URLs, private key material, or full config dumps in memory.

## Common Failure Pattern

The dangerous state is:

```text
live container says: OpenClaw 2026.6.x
Compose image says: openclaw:...2026.5.x
agent runs: docker compose up/recreate/rebuild
result: container comes back from the older image
```

The fix is not better narration. The fix is refusing to mutate until live runtime, durable image, and target version are reconciled.
