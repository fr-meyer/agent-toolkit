# Owned Decision relay module (lane B follow-up)

New source: scripts/github/pullfrog_standalone_decision_relay.mjs.
No CLI or automatic activation. Import startDecisionRelay(options), await the
returned {close}, then await close() at the end of the existing owning operation.

Required options: socketPath, relaySecret, api, owningSignal, pythonExecutable,
qualifyBinding. The API must be an explicitly supplied owned OpenClaw plugin API
with runtime.decisions.evaluate. There is no Gateway HTTP/token path. Owner
AbortSignal is mandatory; disconnect, malformed frames and absolute deadline
abort the actual SDK call signal. No retry, fallback, scheduler or orchestrator.

qualifyBinding is trusted HOST code, never request data. It receives the exact
api/evaluate identity, owning signal and required source contract pin
30786562e236aab6a924981c62aa61b920132c76, agent franck and fixed purpose.
It must independently verify source compatibility and the live owned API binding,
destination authorization and provider/cost admission. It returns a lifecycle
binding with assertAdmissible (rechecked before every SDK dispatch) and release.
No boolean ready flag is accepted. This module cannot attest a plugin API's
origin from duck typing or prove billing from its own code. Missing host verifier
or lifecycle binding refuses startup. Fake verifier in tests is explicitly NOT
qualification. Current installed conceptual docs expose owned SDK evaluation;
installed SDK capabilities reference lacks the Decision section and decisions.js
is an empty runtime export. This is not proof of SDK source compatibility.
Parent must provide independently checked host binding before deployment.

Wire protocol matches existing Python DecisionTransport: newline-framed envelope,
HMAC-SHA256 over exact body bytes, operation/nonce/deadline/payload digest echo.
Only agent franck, fixed purpose/rubric and codec-generated questions are admitted.
Full original body (not a lossy parsed object) is validated by the existing Python
stdlib codec in an explicit absolute interpreter with -I -B, minimal environment,
fixed inline program and local source path. No shell, ambient executable lookup,
provider CLI or untrusted command is used. This preserves Python canonical
hashing and catches duplicate/nonfinite values, full payload and rubric changes.
The actual awaited SDK outcome is passed unchanged to codec validation. A
correlation receipt is created only after that call, using actual outcome hash;
provider/model/runtime provenance is never invented or rewritten.

Limits: Linux private Unix socket only, private same-UID parent directory0700,
socket0600, symlink ancestors and existing paths refused. Node stdlib does not
expose portable SO_PEERCRED; server relies on filesystem access plus dedicated
HMAC secret. Python client independently verifies server SO_PEERCRED. Same UID is
the trust boundary, not a sandbox. No secret should be provisioned in Actions.
No remote ingress. Whole request/reply/validator message maximum131072 bytes;
original codec tighter limits still apply. Deadline at most30 seconds including
validation. The authenticated original timeoutMs must be an integer1..30 seconds
in exact1000ms increments consistent with a codec-valid encoding time at or
before receipt, including request issued/expiry bounds. Transport delay does not
require this original duration to equal newly remaining time. Actual SDK timeout
is always derived from the remaining absolute deadline, never caller duration.
Default4 connections and4 active owned evaluations maximum; configurable
only1..4. Replay cache1024 (configurable1..4096), refuses when full, retains nonce
until deadline. Restart clears replay state; this is not cross-process exactly-once
or billing deduplication. Deployment must not replay requests after restart.
Aborted noncooperative SDK promises retain an active admission slot until settled;
physical provider cancellation remains host/provider responsibility. Every close
caller shares one cleanup promise. Shutdown aborts sockets, awaits all owned
handlers (including codec child reaping and SDK settlement), then releases its
lifecycle binding exactly once. A noncooperative SDK leaves close pending and
the binding held, not a successful cleanup or resource-release receipt. Startup
failures after qualification use the same cleanup, including partial listeners;
preexisting unrelated paths are never removed. Cleanup errors remain observable
to the owning operation awaiting close, not silently converted into acceptance.

Tests: Node built-in suite, Python client to Node fake SDK roundtrip, replay,
agent/purpose/rubric/deadline override, duplicate/nonfinite JSON, MAC and size
refusal, disconnect and owner cancellation, capacity and unknown SDK status.
All SDK callbacks and qualification bindings in tests are fake, no model calls.
Runtime provider readiness, free-cost qualification, exact deployed SDK identity,
plugin installation and service deployment remain parent-owned missing evidence.

## Lossless numeric and original-deadline boundary

Before SDK dispatch the relay recursively refuses unsafe integer Numbers; Python
codec validation applies the same +/-9007199254740991 limit to original exact
input integers and outcome/receipt numbers. No conversion to strings or digest
substitution is used. The codec requires evidence.worker.deadline and refuses a
wire deadline beyond that original controller aggregate bound. Relay timeoutMs is
still reduced to the remaining bounded deadline immediately before SDK invocation.
