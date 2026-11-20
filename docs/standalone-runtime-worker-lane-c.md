# Lane C: live worker qualification, 2026-11-17

## Outcome

Source deliverable complete. Live worker unavailable, deliberately refused.
No CLI/model invocation, ACP session, container launch, installation, credential,
configuration, provider, hosting or remote mutation was performed. Parent retains
hosting/qualification/publication ownership. This is not Workboard execution.

## Read-only evidence in this worker environment

- Python 3.11.2; prlimit and timeout found.
- codex, docker, podman, bwrap, nsjail, firejail and systemd-run absent from PATH.
- cgroup v2 present (cpu, memory and pids controllers among advertised controllers),
  but cgroup.subtree_control not writable by this worker. Controller advertisement
  is not delegated enforcement.
- Native plugin tool discovered via catalog. Official catalog read-only search
  for codex returned response_budget_exceeded/detailsOmitted, not a usable plugin
  identity or interface contract. No installation or activation attempted. This
  does not prove no plugin exists; the parent must resolve the catalog gap.
- No account/auth/environment contents or full process command lines inspected.

## API

scripts/github/pullfrog_standalone_runtime_worker.py exposes:

- inventory(): bounded boolean availability only, no subprocesses or auth reads.
- qualification(): actual local status plus exact blockers, always unavailable
  until a real independently qualified adapter is implemented and reviewed.
- admit(request, plan, profile, current_head_sha=..., now=..., cancelled=False):
  validates the existing exact profile context and refuses live admission. Does
  not consume, refund, reset or replace any reservation. Unknown pre-existing
  consumed state, cost and usage remain null, retry false, reconciliation true.
  No cleanup claim is made, including on cancellation.
- CLI prints the same JSON qualification and exits 2. Exit 2 means unavailable,
  not a successful runtime qualification. Default profile registry remains empty.

Run: python3 scripts/github/pullfrog_standalone_runtime_worker.py

## Why no execution adapter is shipped

There is no inspected live isolation or coding primitive here to adapt. Fork,
setsid, an empty environment, prlimit or timeout cannot establish disk, PID,
network, credential, resource and remote-work boundaries. Existing execution.py
is explicitly not a sandbox. A subscription entitlement or login alone cannot
prove billable fallback is disabled; no inspected subscription-only CLI contract
or independent account-side hard stop establishes that property here. A fake
zero-cost receipt would conceal this gap, not close it.

The checker reports missing binary/delegation blockers plus independent gaps:
immutable CLI/image/build identity, exact resolved model, no-billable-fallback,
aggregate quota and zero-incremental-cost hard stop, CPU/memory/PID/disk/time,
network/credential boundary, trusted recipe/privacy, atomic durable consumed
reservation, cancellation/remote quiescence and independently reconciled usage.

A future fixed adapter must preserve every execution_profile.CAPABILITIES check,
independently authenticated exact context, and durable atomic consumed claim
before effects. Lost/cancelled/ambiguous work retains quota and reconciliation
holds; cleanup and usage require independent observations. This lane does not
invent a weaker replacement registry, success path or receipt issuer.

## Verification and limits

Focused tests cover real-contract valid context refusal, stale head/expiry,
unchanged inputs, unknown billing/usage, cancellation without cleanup claims,
missing primitives, and refusal even when every binary is hypothetically present.
Mocked inventory only tests negative behavior, never establishes live evidence.
Existing profile and worker tests retain atomic claim and usage conservation
coverage. Source tests cannot establish sandbox, entitlement or billing safety.

## Parent handoff

Next No-Manual Run: integrate/review this local source commit and rerun the
qualification checker in the parent-selected host without invoking a model.
Manual Gates: parent-owned exact hosting/credential/provider qualification and
finite live pilot. No new owner approval is inferred from this source deliverable.
Recommendation: keep admission closed until independently verified isolation and
subscription-only no-incremental-billing enforcement exist on that exact host.
