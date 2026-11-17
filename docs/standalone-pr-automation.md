# Standalone explicit-request PR automation

This extends the Pullfrog toolkit, without a new service, CodeRabbit, mandatory
Speculoos or auto-merge. Standalone and Speculoos modes preserve independent
policy gates. This source is **not a qualified hosted coding service**.

## Components and trust

- Immutable request and exact-head binding: pullfrog_standalone_contract.py.
- Explicit actor/command admission and conserved bounded reducer: admission.py.
- Recommendation-only Decision rubric: decision.py; no provider enabled by default.
- Credential-free worker plans, real patch sealing, trusted test/candidate envelopes,
  destination/path guard and ambiguous publication reconciliation: worker.py and
  execution.py. Injected execution ports are not a security/billing sandbox.
- Bounded authenticated full-page review collector and immutable app/account,
  marker, thread and exact-head normalization: collector.py and review.py.
- controller.py joins those contracts and reserves attempts before effects. It
  fixes the A/C reservation convention and verifies D/B/C evidence correlation.

The controller journal uses a per-PR POSIX lock, compare-and-swap, atomic rename
and file/directory fsync. It is a **local persistence seam**, not a distributed
claim service or evidence that ephemeral Actions artifacts are a live claim store.
The authenticated hosted history adapter, retention/inventory integrity and
checkpoint acknowledgement before effects still require qualification. Missing
or ambiguous claim/effect history must never trigger a fresh automatic write.

A provider call is preceded by a persisted decision-start marker. A crash cannot
silently replay it. Publication intent is persisted separately; a restart must
reconcile the precise plan, parent, patch and observed successor before advancing.
Original request digest, usage and attempt limits survive successor heads. Only
CI plus exact current-head Pullfrog and destination evidence can produce
ready_for_human; skip/unavailable do not certify readiness. No code path merges.

## Local interface

The controller accepts **trusted collector/policy data**, never a PR-controlled
bundle. Its CLI deliberately cannot load arbitrary providers or commands:

    python3 scripts/github/pullfrog_standalone_controller.py advance \
      --bundle trusted-bundle.json --journal private-state/pr.json
    python3 scripts/github/pullfrog_standalone_controller.py decide-unavailable \
      --bundle trusted-decision-context.json --journal private-state/pr.json \
      --expected-digest PREVIOUS_JOURNAL_DIGEST

Trusted API seams support isolated fixture providers/executors for integration
tests. Those fixtures do not qualify a real model, credential route, validator,
remote publication, cancellation cleanup or hard billing limit.

## Hosted diagnostic, explicitly disabled by default

Canonical workflow: templates/starter-workflows/pullfrog-standalone-admission.yml;
materialized copy is manifest-owned. It is read-only, pinned to an explicitly
configured immutable controller SHA, never checks out PR code and has no provider,
publisher, credential-write or merge job. The default policy is enabled:false
with an empty initiator allowlist. Both policy and the repository diagnostic
variable must be deliberately configured for an exact approved pilot.

For a qualified diagnostic pilot, set STANDALONE_PR_CONTROLLER_SHA to a reviewed
40-hex commit and STANDALONE_PR_ADMISSION_DIAGNOSTIC=true. Use a trusted policy
with exact canonical repository/immutable actor IDs, protected branches, paths,
budget and enabled:true. An exact /pr-automation run comment or manual PR/task
request is authenticated; normal discussion, forks, PR-author trust alone and
Pullfrog comments cannot initiate. Stable comment/run IDs and original creation
time prevent delivery/rerun from reminting request authority. The summary says
live_execution_allowed:false; the diagnostic is not the coding workflow.

## Remaining live acceptance gates

1. Authenticated durable state/claim history: cross-run serialization, complete
   artifact/run inventory, retention/expiry, cancellation, rollback and checkpoint
   acknowledgement before any effect. Local CAS is not sufficient evidence.
2. Destination-authorized Decision transport/provider and exact runtime identity;
   never place a broad personal Gateway operator token in Actions.
3. One exact coding CLI/model and credential custody route, isolated candidate
   runtime with no publisher credentials, trusted validator/test recipe, included
   entitlement plus independently enforced finite billing/usage hard-stop and
   cleanup/revocation. Received account evidence alone is not qualification.
4. Separate approved publisher with real candidate/patch provenance and ambiguous
   effect reconciliation; authentic Pullfrog numeric app/account IDs and genuine
   all-page live collection. Do not invent IDs or copy synthetic fixture identities.
5. Finite exact repository/PR/head pilot and reviewed acceptance/rollback evidence.
   No auto-merge, protection changes, public visibility change or recurring cost.

Current read-only source assessment favors qualifying one Cursor/Grok route
first, but no exact model/route is claimed operationally ready. These are real
live qualification gates, not GitHub mergeability blockers.

## Validation

    python3 -m unittest discover -s scripts/github/tests -p 'test_pullfrog_standalone*.py'
    python3 -m unittest discover -s scripts/github/tests -p 'test_pullfrog*.py'
    python3 scripts/github/materialize_repo_workflow_templates.py \
      --repo-root . --manifest-path templates/repo-workflow-materialization-manifest.json

Integration fixtures cover real A/B/C/D contracts, publication/restart, unchanged
immutable request, unknown effects, no-provider pause, CAS collision, duplicate
comment, exact-head review, tampering and forbidden authority paths. They do not
contact GitHub, a model, a credential service or a publisher.
