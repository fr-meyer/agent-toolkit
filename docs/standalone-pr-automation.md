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

## Offline runtime-seam follow-up

The runtime-seam source slice adds a typed OpenClaw Decision codec, a transactional-state conformance seam and an execution-profile verification seam. These are source contracts and deterministic fixture boundaries, not a deployed ingress, durable hosted service, sandbox or billing controller. Published heads change only under exact successor publication authority.

- The Decision codec must follow a pinned trusted OpenClaw runtime API source contract. Owning-agent identity is fixed by trusted adapter code, not task text. Model aliases do not prove checkpoint custody; missing usage and cost remain unknown. There is no provider invocation, broad Gateway HTTP transport or credential in this module.
- The state seam exercises trusted in-process reducers, slot/request identity, CAS, sequence/fence and acknowledgement continuity. Fixed controller operations may replace a prior attempt’s decision, worker-plan and publication-receipt slots only under exact phase/lineage checks; current pending intent and immutable historical documents remain retained. Its memory-only fixture backend is not durable across restart and cannot authorize a hosted effect. Missing or unavailable history is never evidence of an empty slot. Unknown effects retain their hold and spent reservations.
- The execution-profile seam requires trusted independent receipt verification and atomic reservation consumption ports. A monetary limit may be exact integer zero; all nonmonetary limits remain strictly positive integers. Receipt context/reservation comparisons retain integer identity, so booleans or floating zero do not impersonate zero-charge custody. Actual usage/cost remains independently reported or unknown, never inferred from a ceiling. Its default registry is empty; it implements no CLI, sandbox, quota account or remote cancellation. Self-attested booleans, a JSON digest and post-response cost checks do not establish security or billing enforcement.

Confirmed exact publication reconciliation applies canonical successor and cumulative usage before time or event-cap terminalization. At the 256-event limit, the retained audit prefix remains unchanged and the controller journals the receipt; no new attempt is authorized. An already-terminal controller journal remains a manual reconciliation hold, not an automatically reopenable workflow. Cancellation and ambiguous effects never imply replay permission.

Before a live pilot, select and authorize exact hosting/ingress/storage, destination disclosure, coding CLI/build/model/custody and entitlement, enforceable aggregate usage/cost limits, isolation/resource envelope, separate publisher and a finite repository/PR/head activation. No provider call, additional spending, credential/configuration change, deployment, autonomous publisher or merge is authorized by source tests.

## Opt-in next-action routing v2 (source only, 2026-11-20)

The existing controller exposes route and a provider-free route-unavailable
diagnostic. V1 three-way recommendations remain unchanged. V2 has exactly one
next_action: implement_fix, retry_ci, request_review, wait, no_action, ask_human.
The codec explicitly negotiates v2; the fixed transport/relay validates using
that codec. Only implement_fix bridges losslessly to the existing guarded worker.
No_action is not readiness certification. Ask_human pauses. Operational failures,
refusal and cancellation remain non-success, never no_action.

Retry CI and review-request executors are unavailable here: neither action is
offered or dispatched. Needed ports must bind exact run/head eligibility,
allowances, persisted dispatch identity and independently read-back receipts,
never model-selected commands or workflows. No fabricated ready adapter exists.
A running dependency deterministically waits without a model call. An existing
verified Pullfrog completion event resumes this path; CI completion collection
remains unavailable. There is no scheduler or polling. Admission conservatively
consumes an attempt even when it subsequently waits, without budget refunds.

CAS journaling precedes provider calls. Interrupted calls remain reconciliation
holds, not retries. Original deadline, attempts, destination and successor-head
controls and existing publication reconciliation remain in force. Usage/cost
qualification remains mandatory: source does not prove entitlement, actual zero
cost, enforceable upstream caps, real-event quality or live readiness. No runtime
setup, provider calls, remote writes, activation or workflow edits occurred.

### Routing repair: typed CI and concrete fixed effects

This section supersedes the earlier missing-handler inventory. Production code
is in scripts/github/pullfrog_standalone_actions.py. Actions accepts the existing
pullfrog_review_fallback.GitHubClient (get/post/graphql), backed only by the
host's already-approved GitHub auth. No credentials are discovered or configured.
Trusted policy fixes ci_run_id, ci_workflow_id, max_ci_retries, pullfrog_identity,
review_workflow_id, review_trusted_ref (tags/<qualified lightweight tag>) and
review_trusted_sha. None may originate in PR/model/webhook prose. Tag must resolve
to the accepted commit and be protected against mutation by qualified runtime
controls. No tag is created by source implementation.

CI GETs /actions/runs/{id}, exact attempt /jobs pages and PR identity before and
after collection. Repository/head/workflow/event/attempt identities must agree.
Only timed_out/startup_failure jobs with no code-failure jobs qualify transient
retry, and max_ci_retries bounds run_attempt. The sole retry POST is the existing
/actions/runs/{id}/rerun-failed-jobs with empty body. No workflow name or command
is model-supplied. A higher independently fetched run_attempt proves effect;
unchanged/unknown observation retains the hold and does not authorize retry.

The concrete PullfrogWorkflowRunner dispatches only the existing pullfrog.yml
interface, with inputs prompt/name, via the verified workflow ID. Fixed prompt
contains validated PR/base/head identity, never task/model text. Existing workflow
pins pullfrog/pullfrog@25a837a2b078177c3acdce790506d1fd1acedd82, disables push,
restricts shell and disables progress comments. Serving-source, credentials,
permission and spending qualification remain required; this code does not enable
a workflow or claim that its installed token can submit a review. The existing
trusted collector independently validates exact-head Pullfrog account/app/checks
and completed review. Dispatch success is never accepted as review completion.

Controller route(..., actions_port=Actions(...)) offers only observed eligible
actions, journals intent as action_pending, then dispatch_action commits
 action_started before any POST. reconcile_action only reads effects, never
reinvokes. Unknown network effects or process loss remain held. Review intent
includes the pre-dispatch review digest; the same previous review cannot prove
new work. Retry receipt carries the successor attempt as typed CI dependency.
complete_ci accepts no event-provided status: it fetches the retained exact run
and attempt, passes the bound observation to the existing reducer, deduplicates
semantically and reserves a bounded successor attempt for meaningful post-CI
routing. Generic dependency_running is rejected; no polling/scheduler is added.
Host completion events call complete_ci only for retained dependencies. Cancel
and original time/attempt/cost limits remain authoritative. No source test claims
provider billing, live dispatch, protected-tag policy or hosted durability proof.
