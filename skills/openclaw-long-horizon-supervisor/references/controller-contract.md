# Optional controller extension contract

Use this reference only when a task needs fail-closed intent tracking and fenced effect metadata beyond Workboard plus the native service preview/confirm or compare-and-swap API. Workboard remains the durable task ledger. This controller does not make external effects exactly once because it does not own the provider call. If exactly-once external effects are required, proceed only when the effect boundary supplies service-side idempotency, deduplication, or fencing plus conclusive receipt reconciliation; otherwise stop at the unsupported guarantee.

The environment-provided controller should support equivalent operations for:

- initialize without overwrite and validate its descriptor/state;
- claim, renew, and release a fenced operation lease;
- record a stable non-idempotent intent before execution;
- record an outcome receipt as `succeeded`, `failed`, or `ambiguous`;
- bind an exact manual gate to action, mutable identifiers, approver, reference, revision, and expiry;
- expire and consume approvals;
- repair interrupted state/event-journal writes;
- export a bounded receipt that can be attached to Workboard proof.

Validation must fail closed on:

- unknown or malformed descriptor, state, event, intent, gate, or pending-journal fields;
- project/card identity mismatch;
- lease id, owner, fencing epoch, or expiry mismatch;
- gate hash, revision, mutable-identifier, approver, reference, or expiry mismatch;
- receipt without the matching fenced intent;
- duplicate event or operation ids;
- stale owners attempting release or receipt publication.

State writes should be atomic and single-writer. Event recovery must not create duplicate records. A surviving intent without a conclusive receipt is ambiguous and must not be replayed automatically.

The controller manages effect metadata only. It must not execute project commands, call providers, modify Workboard or Automations outside the authorized lane, infer approvals, or grant authority beyond repository/user policy. Record its bounded receipt on the claimed Workboard card, then complete, block, or release that card through the normal workflow.
