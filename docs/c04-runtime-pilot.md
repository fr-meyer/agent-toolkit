# C04 synthetic runtime pilot — source prepared, execution not authorized

This public, provider-free experiment is NOT general worker qualification. Original
C04 boundary code, C03 integration and C05 providers remain separate checkpoints.
No real candidate source, private Speculoos code, model calls, credentials, lease
issuance, repository writes or deployment are part of this pilot. Passing the
synthetic probes cannot set a runtime profile to qualified.

## Activation and approval

Canonical source: templates/starter-workflows/c04-runtime-pilot.yml. Runtime copy:
.github/workflows/c04-runtime-pilot.yml. Materialization is explicit; there is no
reusable-workflow ref to diffuse, so ref-sync bindings remain unchanged.

The workflow triggers only on pushes to feat/c04-provider-free-pilot-20261110. The job
runs only for the original branch creation event (not subsequent pushes), and
only for run attempts 1–3. No automatic retry, schedule, dispatch or PR trigger
exists. Publishing the new branch starts its first run immediately; therefore
exact branch/head publication AND that immediate run must be approved together.
At most two reruns of that same original event are within the proposed three-run
cap; do not delete/recreate the branch to reset the limit. No PR or merge is
needed for this feature-branch push pilot. Repository policy still requires a
separate feature-to-dev PR before any eventual integration; this experiment
authorizes neither integration nor a bypass of default-branch protections.

An operator must verify standard hosted Linux/public-repository free eligibility
before publication; no larger runner, paid service, account login or billing
fallback is allowed. GitHub Actions and the fixed public container image are
permitted only within exact later upload/run approval. Anonymous image pull
failure or Docker unavailability stops immediately, without install or login.

## Fixed synthetic workload

One standard ubuntu-24.04 GitHub-hosted job, timeout five minutes. The supervisor
has a 180-second outer deadline plus ten-second kill grace; cleanup is bounded
to thirty seconds plus five-second grace. Four containers run sequentially, not
a matrix: baseline boundary checks, bounded PID exhaustion, bounded OOM and a
three-second supervised timeout. No container exceeds one CPU, 128 MiB memory,
32 processes or 16 MiB tmpfs. OOM allocation is capped at twenty 16 MiB chunks;
PID probe attempts at most forty small sleep processes. The timeout fixture
sleeps for sixty seconds but the external supervisor stops it after three.

The image is the exact linux/amd64 official Python manifest:
`docker.io/library/python@sha256:0f086103b026048cc50cb5da25ec435c023c5241a83fc44daea593377abc61c4`.
It was observed from public Docker Hub tag metadata on 2026-11-10; that is not
a security qualification or signature attestation. No mutable image fallback.
Host runner image version, Docker server, kernel, local image ID, workflow/head,
run ID/attempt and fixture digest are recorded for later external readback.

Containers use no network, no capabilities, no-new-privileges, UID/GID 65534,
read-only root and a single read-only synthetic probe-file mount. No checkout,
host root, Docker socket or credential directory is mounted into the container.
The trusted host supervisor uses the runner Docker daemon: it is NOT exposed to
the fixture. The Docker client drops all ambient environment except fixed PATH
and a private empty HOME/config directory, so it cannot use a user Docker auth
cache, daemon override or provider credentials. Only the checkout action uses
the platform read-only token; persist-credentials, submodules and LFS are false.

The supervisor checks real Docker configuration before every start, independently
observes exit/timeout/OOM attribution and verifies teardown. Known synthetic
fixture results supplement those checks; fixture stdout alone cannot certify
general candidate safety. A host-only dummy sentinel exists but is not mounted.
Removal is restricted to exact names with this run/attempt label, never global
prune or unrelated containers/images. The always-run workflow cleanup retries
only that same bounded teardown if the supervisor was interrupted. GitHub hard
runner cancellation can still prevent finalizers; absence of clean teardown
evidence must remain a failed/incomplete result, not assumed success.

## Evidence and explicit remaining gaps

A small sanitized JSON receipt is printed by trusted supervisor and stored in
RUNNER_TEMP for the life of the job; no artifact upload, prompt, raw environment,
credential values or Docker inspect dump is published. Existing GitHub log
retention is not changed. Inspect log/run identity independently before using
the receipt: environment variables and JSON labels are NOT authentication.

Even a passing pilot records runtime_qualified=false and
production_authorized=false. Credential-lease revocation, general hostile
candidate admission, CPU-saturation enforcement and independent workflow-identity
attestation remain unobserved. Do not populate C03/C04 qualification registries
from a passing pilot alone. Missing/failed probes, unknown context, changed image,
unsafe mounts/privileges, unavailable cleanup or exhausted attempts block.

Local tests mock all Docker calls and exercise exact policy, failures and cleanup;
they do NOT pull an image or run hosted/resource probes. Full actionlint is still
a separate validation if unavailable locally; YAML/shell checks are not its
equivalent. The CLI refuses ordinary local use; never forge Actions context to
run it in the live Gateway.
