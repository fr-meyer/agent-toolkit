# Lane B: fixed Decision transport, 2026-11-17

## Actual availability

Installed read-only documentation: /app/docs/concepts/decision-models.md and
/app/docs/gateway/tools-invoke-http-api.md. Installed bundled implementation:
/app/dist/openclaw-tools-CIbsAgLY.mjs (Decision tool, approximately lines 3433-3540).
The installed tree has no /app/src. The tool validates only state/questions,
binds its trusted calling agent, selects the agent's effective Decision model,
and returns typed results in tool details (unavailable adds guidance).
It computes its own hashed rubricVersion. Therefore direct tools/invoke is NOT
compatible with the existing codec's fixed rubricVersion/purpose receipt.
Do not rewrite that provenance to make it appear compatible.

The documented HTTP POST /tools/invoke accepts tool, args and agentId/sessionKey,
returns {ok:true,result}, and uses Gateway auth plus tool policy. Shared-secret
bearer auth is full operator authority, even with a narrow scopes header. It is
not an acceptable Actions credential. Identity-bearing proxy modes can honor
scopes but their availability and a fixed-operation identity grant were not
proved here. No existing narrowly authenticated external Decision endpoint was
proved. No live provider call, credential read or configuration change occurred.

## Implemented API

scripts/github/pullfrog_standalone_decision_transport.py exports:

- DecisionTransport(socket_path, relay_secret=..., destination_authorized=False,
  clock=time.time, cancelled=lambda:False), a callable provider(payload).
- last_receipt, reset before every attempt, set only after authenticated reply
  correlation and the existing typed codec validate. Cost remains unknown.
- TransportError(ValueError), cancellation raises CancelledError. Other socket
  failures propagate; decision.evaluate already sanitizes provider failures.

This is a private Linux AF_UNIX client, not a claim that a relay exists. Socket
and private parent directory must belong to the current UID, socket mode0600,
directory mode0700. Symlink ancestors are refused; SO_PEERCRED same UID is
mandatory. No URL/redirect/network/provider override exists. Same-UID processes
are trusted, not isolated from each other. A dedicated high-entropy relay secret
is required (minimum32 printable ASCII characters, entropy supplied by operator).
No Gateway secret is accepted or needed by this protocol.

## Relay wire v1 (new internal protocol, not an OpenClaw endpoint)

One newline-terminated JSON envelope per connection, maximum131072 bytes in each
direction, with exact fields body (JSON string), mac (HMAC-SHA256 hex of exact
UTF-8 body bytes using the dedicated secret). Duplicate JSON keys and nonfinite
JSON values fail. Request body has operation=pullfrog.standalone.decision.v1,
nonce=random256bits hex, integer deadline epoch seconds (at most30 seconds),
payload_digest, batch and options from codec.encode. Response body must have
exact operation/nonce/deadline/payload_digest echo, outcome and trusted_receipt.
No caller-supplied outcome is accepted. Existing codec validates status, answers,
provider/model provenance and complete payload/outcome digest receipt. The client
never synthesizes trusted_receipt or provider provenance. MAC authentication
proves relay possession of a secret, NOT truth of a model claim by itself.

Parent must implement/qualify the trusted host relay using an owned plugin
operation calling api.runtime.decisions.evaluate(batch, {agentId:'franck',
purpose:'pullfrog.standalone.recommendation', rubricVersion: codec version,
timeoutMs, signal}). The host must independently validate the fixed operation,
full codec payload/rubric, MAC, deadline, nonce replay cache, peer identity,
destination permission and zero-incremental-cost/provider qualification. It must
capture the untouched actual outcome from that owned call, then create the
codec correlation receipt (source_pin, agent_id, purpose, payload_digest,
outcome_digest). source_pin must be a verified compatible source contract, not
a fabricated runtime version. Never generate an ok receipt from labels or
fixtures. No arbitrary tools, sessions, agent IDs or model parameters allowed.

Disconnect and deadline must abort the host operation using its live signal;
client cancellation closes the socket within its bounded100ms receive polling.
There are no retries, fallback work or background dispatch. Client validation
runs again after receipt/decode; late/unknown/malformed results never escape as
recommendations. Cancellation after dispatch alone cannot prove provider work
stopped, so the relay abort implementation is a mandatory qualification gate.

## Verification and remaining gates

Focused stdlib tests use a temporary local fake socket relay and fixed fixtures,
not an external call. They test typed roundtrip, MAC/provenance/correlation
refusal, duplicate/invalid/oversize JSON, forbidden URL destinations and missing
authorization, and pre-I/O cancellation. Full Decision suite is also run.
No source test establishes runtime readiness, billing qualification or remote
Actions reachability. No relay service, SDK binding, credential provisioning,
remote private ingress or deployment was created. Those are concrete missing
capabilities owned by parent. Keep default profile registry empty. An Actions
runner cannot use a Unix socket on another host; parent must choose a qualified
same-host worker or separately reviewed scoped ingress, not expose Gateway auth.
