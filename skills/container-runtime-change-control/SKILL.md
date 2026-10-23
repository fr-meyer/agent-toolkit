---
name: container-runtime-change-control
description: Use this skill before restarting, recreating, rebuilding, upgrading, rolling back, or repairing a containerized service. Apply it to Docker, Docker Compose, Kubernetes, systemd-managed containers, plugin/tool deployments, and runtime repairs where live software version, deployment image/spec, running container image/digest, target version, and rollback path must be reconciled before mutation.
---

# Container Runtime Change Control

## Goal

Prevent accidental rollbacks, image drift, and non-durable hotfixes in containerized services. Treat container lifecycle work as a change-controlled operation whenever a restart, recreate, rebuild, upgrade, rollback, plugin install, runtime repair, or tool deployment can affect a live service.

This skill is intentionally generic. Service-specific commands, image variable names, deployment roots, and health checks belong in local runbooks or caller-supplied context.

## Hard Rules

- Start read-only. Do not restart, recreate, rebuild, pull, install, patch config, or kill processes until preflight evidence is collected.
- Reconcile the deployment truths before mutation:
  - live software version from the running service, if the service exposes one;
  - desired target version, or explicit statement that the live version should be preserved;
  - durable deployment image/spec, such as Compose env image, Kubernetes image, Helm value, systemd unit, or deployment manifest;
  - actual running container image tag and digest/ID when container tooling is available;
  - rollback path, such as previous image tag, image archive, registry copy, manifest backup, VM snapshot, or explicit `rollback unavailable`.
- Before touching a container image through pull, build, tag replacement, upgrade, rollback, or recreate from a changed spec, preserve or identify a known-good rollback image first. Prefer both a fast rollback tag and a durable copy when practical.
- If the live version and the image/spec used for recreate disagree, stop before any recreate/rebuild/restart that could switch versions.
- Treat image tags, Compose env values, and mutable registry tags as labels, not proof of binary version. If a service exposes a version command, verify the version inside any pulled or built candidate image before using it to recreate the live service.
- For tool-only runtime changes, such as adding shell, media, network, or validation utilities, prefer a derived image built from the current official/runtime image. Do not rebuild the application from a source checkout unless source rebuild is the explicit approved goal.
- A source-checkout build is allowed only when preflight proves the source checkout version, intended target version, durable deployment image/spec, running image, and live service version are reconciled. If any of those disagree in a way that could change the service version unexpectedly, classify the state as `version-drift-blocker`.
- Do not treat package installs or source edits inside a running container as durable deployment state unless they are baked into the image or explicitly recorded as temporary hotfixes.
- Prefer orchestrator-level changes over in-container process kills. Use ad-hoc process kills only for emergency recovery, and record them as such.
- Preserve unrelated user/parallel-agent work and runtime config. Never use destructive cleanup as a shortcut to make a deployment proceed.

## Default Workflow

### 1. Declare Intent

State the operation before writing anything:

- operation type: inspect, restart, recreate, rebuild, upgrade, repair, rollback, plugin change, or tool deployment;
- intended version, or explicit statement that the current live version should be preserved;
- affected service/container;
- deployment source: Compose env, Compose YAML, Kubernetes manifest, Helm values, systemd unit, image tag, or other;
- rollback path.

If the target version or durable deployment source is unknown and the operation can recreate a container, inspect trusted local notes or ask before proceeding.

### 2. Run Preflight

Collect evidence read-only. Prefer the bundled helper when local paths are available:

```bash
<skill-dir>/scripts/container-runtime-preflight.sh \
  --live-version-command 'my-service --version' \
  --deployment-env /path/to/service/.env \
  --image-var SERVICE_IMAGE \
  --container my-service \
  --operation recreate \
  --target-version 1.2.3 \
  --rollback-artifact 'image-tag=my-service:backup-YYYYMMDD-HHMM' \
  --strict
```

You can also pass an image directly:

```bash
<skill-dir>/scripts/container-runtime-preflight.sh \
  --live-version-command 'my-service --version' \
  --deployment-image 'registry.example.com/my-service:1.2.3' \
  --container my-service \
  --operation restart \
  --target-version 1.2.3 \
  --rollback-artifact 'archive=/var/backups/my-service-image-YYYYMMDD-HHMM.tar.zst' \
  --strict
```

If the helper cannot model the deployment source, gather equivalent facts manually using platform-native commands such as:

```bash
docker inspect --format '{{.Config.Image}} {{.Image}}' <container>
docker compose config
kubectl get deployment <name> -o yaml
helm get values <release>
systemctl cat <unit>
```

Keep the operation read-only until the comparison is understood.

For source-based Docker or Compose rebuilds, also collect the source version from the service's native metadata before mutation, such as `package.json`, `pyproject.toml`, `Cargo.toml`, image labels, a release manifest, or an equivalent version file.

If a source rebuild is approved, split build from recreate and verify the candidate image version first:

```bash
docker compose build <service>
CANDIDATE_IMAGE="$(docker compose config --format json | jq -r '.services["<service>"].image')"
docker run --rm --entrypoint sh "$CANDIDATE_IMAGE" -lc '<service> --version'
docker compose up -d --no-build <service>
```

Run the final recreate only when the candidate image version matches the intended target. If the candidate version cannot be checked, stop and classify the operation as `read-only-only` or `version-drift-blocker` based on the evidence.

### 2.5 Capture or Verify the Rollback Image

For Docker-style image mutation, do this before any build, pull, tag switch, recreate from a changed spec, upgrade, or rollback:

- record the current image reference and immutable image ID/digest;
- preserve the deployment env/manifest that points at the current image;
- create a fast local rollback tag for the current image when the platform supports it;
- when storage and policy allow, create a durable image archive with `docker save` and compression, or copy the image to a registry/object store;
- write a small manifest beside the archive or in the change record with image ref, image ID/digest, archive path or registry ref, checksum, creation time, and restore command;
- verify the rollback artifact is readable before proceeding.

Do not put secrets, signed URLs, registry tokens, or credential-bearing paths in `--rollback-artifact`; the helper prints the value as change evidence. If rollback is unavailable, say so explicitly in the human report, but do not expect strict preflight to pass.

Portable Docker examples:

```bash
docker inspect --format '{{.Config.Image}} {{.Image}}' <container>
docker image tag <current-image-ref-or-id> <service>:backup-YYYYMMDD-HHMM
docker save <service>:backup-YYYYMMDD-HHMM | zstd -T0 -o <backup-dir>/<service>-image-YYYYMMDD-HHMM.tar.zst
sha256sum <backup-dir>/<service>-image-YYYYMMDD-HHMM.tar.zst > <backup-dir>/<service>-image-YYYYMMDD-HHMM.tar.zst.sha256
```

Use an available compression tool such as `zstd` or `gzip`; do not install packages as part of the backup step unless that package change is itself approved.

If a local archive is too large, use the strongest available substitute: a registry copy, cloud snapshot, or documented previous image tag plus manifest backup. If no rollback artifact can be created, classify the operation as `read-only-only` or explicitly report `rollback unavailable` and ask before continuing.

### 3. Classify the State

Use one primary status:

- `safe-to-proceed`: live version, target version, durable deployment image/spec, and running image are reconciled for the requested operation.
- `needs-image-update`: target version is known, but the durable deployment image/spec does not yet carry it.
- `version-drift-blocker`: live version, deployment image/spec, or running image disagree in a way that a restart/recreate/rebuild could change versions unexpectedly.
- `read-only-only`: required evidence is missing, platform access is unavailable, or the requested operation is only an audit.
- `rollback-required`: the intended action is recovery to a known prior image/snapshot and must be stated explicitly.

Stop on anything except `safe-to-proceed` unless the user changes the goal to read-only diagnosis, updating the deployment image/spec, or an explicit rollback.

### 4. Execute the Smallest Approved Change

Prefer durable deployment paths:

- update image tags, manifests, Helm values, Compose env files, or overlays intentionally;
- use the orchestrator's normal lifecycle command;
- keep config/env/manifest backups before mutation;
- keep the pre-change image rollback tag/archive/registry copy/snapshot until post-change verification passes and the operator explicitly accepts the new baseline;
- separate image/runtime changes from unrelated config/model/plugin changes when practical;
- make one risky change at a time and verify before continuing.

Do not hide version drift by restarting harder.

### 5. Post-Change Verification

After any mutation, verify:

- live software version;
- durable deployment image/spec;
- running container image tag and digest/ID;
- service health endpoint, CLI status, logs, or platform readiness;
- any touched plugin/tool/model/runtime surface;
- rollback artifact still exists, has a recorded restore command, and remains usable if rollback remains relevant.

If post-change state differs from the intended target, stop and report. Do not stack additional repairs without a new preflight.

### 6. Record the Change

Write a compact durable note in the caller's normal operations log, including:

- operation and target version;
- preflight status and key version/image evidence;
- files/manifests/images/configs changed;
- rollback path;
- post-change verification results;
- remaining warnings or follow-up actions.

Do not store secrets, raw tokens, signed URLs, private key material, or full config dumps in memory.

## Common Failure Pattern

The dangerous state is:

```text
live service says: version B
durable deployment image says: version A
agent runs: restart/recreate/rebuild
result: container comes back from version A
```

The fix is to refuse mutation until the live service, durable image/spec, running container, target version, and rollback path are reconciled.

Another dangerous state is a disguised rollback:

```text
live service says: version B
image tag/env says: version B
source checkout actually builds: version A
agent runs: docker compose up -d --build
result: service comes back from version A while the tag still looks like B
```

The fix is to stop on source/version drift. For tool-only additions, build a derived runtime image instead of rebuilding the application from source.
