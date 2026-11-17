# Lane A: local transactional SQLite journal

Source: scripts/github/pullfrog_standalone_sqlite.py. Python standard library only.
This is local source qualification, not hosted, provider, billing, or deployment
qualification. No registry, workflow, existing module, credential or service is
changed. Authority is the owner-approved 2026-11-17 22:13 KST native-session lane.

## API

Import SQLiteBackend, Store and ControllerAdapter from
pullfrog_standalone_sqlite (with scripts/github on the Python import path).

- SQLiteBackend(path, repository, pr_number, create=False): one exact PR slot
  per file. create=True exclusively provisions a new 0600 file. Existing files
  cannot be reprovisioned. Opening a missing file, failed provision, absent
  schema, corrupt bytes or inconsistent identity refuses. Parent directories
  must already exist and be trusted. read() returns the latest receipt or None
  for a positively provisioned empty slot. records returns a validated detached
  full history snapshot, never a mutable backend collection.
- Store(backend, trusted_reducers=(), generation=1).transaction(expected_digest,
  transform): identical reducer contract to the existing Store. Only explicitly
  registered exact Python callable identities are accepted. These are trusted,
  synchronous, in-process pure reducers, not a wire protocol or sandbox.
- ControllerAdapter(backend, generation=1): same fixed advance, decide,
  bind_publication and reconcile signatures as the existing ControllerAdapter.
  Its private proxy is revoked on success or exception. There is no public
  arbitrary transaction/operation dispatcher.
- acknowledge results retain the existing journal_digest/output/changed/ack
  shape. durability is local_sqlite_full, hosted_effect_allowed is always
  False. authorize_hosted_effect always raises hosted_store_unqualified.
- lose_next_ack is a test-only fault switch: the next completed transaction
  commits to the actual file but withholds output and raises
  ambiguous_ack_reconcile_required. It never creates qualification evidence.

## Integrity and mutation design

Each transaction uses a fresh independent connection, BEGIN IMMEDIATE, and
synchronous=FULL. Only SQLite delete or WAL journaling modes are accepted.
Rows contain the original canonical receipt bytes, including complete document,
sequence, previous digest, generation and slot-bound acknowledgement identity.
The slot and latest canonical receipt are stored separately in metadata. Reads
use one snapshot and validate the entire chain, acknowledgements, canonical
encoding, slot identities and retained head before any reducer runs.

Under the database write lock the bridge loads an exact FixtureBackend and
invokes the real existing Store.transaction. It does not copy or weaken the
validation/reducer rules. Only a successful changed result appends one immutable
receipt and updates the retained head in the same SQL transaction. No-op outputs
still require the existing durable receipt and matching fence. Capacity remains
1024 retained records with no expiry, compaction or reset endpoint. Controller
scope is the existing private operation capability, so valid second-attempt
artifact transitions pass the same restrictions as the original adapter.

COMMIT precedes acknowledgement/output release, followed by validated readback.
Commit errors are ambiguous holds. Every other storage/readback exception also
withholds output; callers must treat all such failures as stop/reconcile, never
as permission to retry an effect. Concurrent advancement after commit can cause
readback mismatch and an intentionally conservative ambiguous hold. Restart uses
persisted generation, original request/budget and history, not an inferred fresh
request. The API has no automatic provider/publication retry on ambiguity.

## Tests and evidence

Focused tests use actual temporary files, real Store validation and actual
controller reducers. Coverage includes independent-connection CAS contention,
canonical bytes, reopen, wrong repository/PR, missing/reprovision refusal,
generation takeover, budget/time-origin retention, untrusted reducer denial,
corruption/truncation, reducer rollback, failed SQL head update atomic rollback,
process exit during an uncommitted SQL mutation, process exit after real Store
commit, ambiguous acknowledgement before Decision and after completion, unknown
publication holds, and two complete attempts with retained first-attempt history.
Controller fixtures/providers remain offline test code, not runtime evidence.

Run:

    python3 -m unittest discover -s scripts/github/tests -p test_pullfrog_standalone_sqlite.py -v
    python3 -m unittest discover -s scripts/github/tests -p 'test_pullfrog_standalone*.py'

## Explicit remaining qualification gaps

The existing core Store accepts only exact FixtureBackend and unconditionally
denies hosted effects. This module composes that Store under a real SQLite
transaction rather than monkeypatching it, subclass-spoofing its fixture type,
or minting a hosted-qualified class property. It is not accepted by a hosted
registry and does not authorize any live effect. Parent integration must retain
that refusal until independently qualified storage/effect authority exists.

SQLite FULL and process tests do not prove machine power-loss survival, durable
host volume semantics, backup retention, disaster recovery, replicated storage,
filesystem locking across network mounts, or external anti-rollback. The parent
must establish those on the actual host and trusted storage before qualification.
In particular a coherent whole-database rollback/replacement, or a matching
rollback of both journal and metadata, cannot be detected without an independent
monotonic checkpoint/backup inventory. File/directory access control is part of
the trust boundary; this is not tamper-proof storage against a privileged writer.
Do not restore an old database and resume effects. Hold, compare independent
checkpoints and reconcile external identities/effects first. Local transactions
and redundant head metadata only detect incomplete/truncated local history,
not a coherent adversarial historical snapshot. No backup or hosting mechanism
was fabricated to conceal this limitation.

Provisioning is explicit and leaves failed files for diagnosis. If the file is
missing on restart, do not pass create=True: that would be an operator-authorized
new slot, not recovery evidence. Host provisioning and backup must independently
retain slot existence even across filesystem loss. Hardware/OS synchronization
and directory persistence remain host-qualification requirements.

## Lane closeout evidence (2026-11-17)

- Focused SQLite integration suite: 20 tests passed.
- All standalone suites: 207 tests passed.
- Python compilation and staged whitespace validation passed.
- Tests are source/local file evidence only. No host runtime, billing,
  backup, power-failure, provider or publication qualification is claimed.
- Only this new adapter, its focused test module and this lane report changed.
