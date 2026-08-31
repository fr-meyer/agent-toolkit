# Controller adapter contract

Use this reference when registering, auditing, or recovering a durable project supervisor.

The environment-provided controller should support equivalent operations for:

- initialize without overwrite and validate descriptor/state;
- render canonical recurring-watchdog and one-shot-wake declarations;
- bind and verify exact scheduler identities;
- check whether work is due;
- claim, renew, and release a fenced lease;
- record/deduplicate external signals and queue signals during a lease;
- record non-idempotent operation intents and receipts;
- raise, approve, expire, and consume exact manual gates;
- update notification routing only from an interactive lane;
- repair interrupted state/event journal writes.

Validation must fail closed on:

- unknown or malformed descriptor, state, event, signal, or pending-journal fields;
- project-id mismatch;
- scheduler payload/session/tools/delivery/schedule drift;
- lease id, owner, epoch, or expiry mismatch;
- gate hash, revision, mutable-identifier, approver, reference, or expiry mismatch;
- operation receipt without the matching fenced intent;
- event payload collisions with reserved envelope fields;
- duplicate event ids outside any bounded recent cache.

State writes should be atomic and single-writer. Event append recovery must not create duplicate records. An expired or stale lease holder must be unable to release or record receipts. A queued signal must override a requested terminal or gated release to a resumable state.

The adapter manages control metadata only. It must not execute project commands, infer approvals, call providers, or grant authority beyond the surrounding repository/user policy.