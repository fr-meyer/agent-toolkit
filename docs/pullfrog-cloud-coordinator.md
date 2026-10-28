# Pullfrog cloud coordinator

The target architecture is an unattended, bounded loop:

```text
Pullfrog review
  -> provider-free exact-head decision
  -> Pullfrog remediation when authorized
  -> new exact head
  -> fresh Pullfrog review and independent checks
  -> repeat until clean or stopped
```

Pullfrog remains the sole AI reviewer and intended fixer. The coordinator is repository-owned orchestration only. It does not replace Pullfrog with another reviewer, provider, service, or fork.

## Current dry-run boundary

The current implementation is deliberately non-mutating:

- evaluator: `scripts/github/pullfrog_cloud_coordinator.py`
- exact-head decision core: `scripts/github/pullfrog_cycle_contract.py`
- remediation destination guard: `scripts/github/pullfrog_destination_guard.py`
- canonical workflow: `templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml`
- live materialized workflow: `.github/workflows/pullfrog-cloud-coordinator-dry-run.yml`

The workflow reads GitHub state with only `checks: read`, `contents: read`, and `pull-requests: read`. It never invokes Pullfrog or a model and cannot fix, commit, push, approve, merge, rerun, release, deploy, alter settings, or delete a branch. It uploads only a sanitized decision receipt.

A receipt can report `would_action: start_remediation`, but it always records `executed_action: none` and every mutation flag as `false`.

## Write-capable implementation, not yet activated

The repository now also contains the separately gated implementation of the unattended mutation stage:

- trusted remediation controller: `scripts/github/pullfrog_cloud_remediation.py`
- canonical workflow: `templates/starter-workflows/pullfrog-cloud-remediation-loop.yml`
- live materialized copy: `.github/workflows/pullfrog-cloud-remediation-loop.yml`

This source is implemented and locally validated, but publication, default-branch activation, and the first hosted write pilot remain separately authorization-gated. Merely preparing or committing this branch does not authorize a hosted run.

The workflow has four permission-separated jobs:

1. **Evaluate and claim** uses read-only GitHub permissions. It reloads bounded, workflow-bound artifact history, emits the validated nested history record separately from the full ledger, evaluates fresh exact-head Pullfrog/CI/Speculoos evidence, uploads a durable idempotent claim before provider invocation, and uploads the sealed native dispatch as a separate transient artifact. Keeping `claim.json` as the durable claim artifact's only file preserves deterministic ledger reconstruction.
2. **Remediate locally** has `id-token: write` for provider routing but only the job-scoped read token for GitHub. The workflow maps that built-in token as `GH_TOKEN`, forcing Pullfrog to reuse it instead of minting its normal write-capable MCP installation token. It sends Pullfrog `v0.1.102` the native `fix_review` dispatch envelope (`issue_number`, exact `review_id`, `approved_only: false`, and `authorPermission: none`) through the exact `prompt` input. Pullfrog has `push: disabled`, `shell: restricted`, progress comments disabled, no gh CLI token or cross-run learning writes, and no content, pull-request, check, action-dispatch, or publication write authority. This job exports only untrusted action output and an untrusted raw patch.
3. **Validate and seal** starts in a separate read-only job with a fresh trusted default-branch controller checkout and a fresh exact-source checkout. It re-reads the live PR identity, parses the bounded structured result, applies the raw provider patch to the fresh source, rejects forbidden paths and gitlinks, and emits a canonical digest-bound patch plus candidate record. Provider processes and modified provider-job files cannot cross this job boundary.
4. **Publish** has no provider identity token. It alone receives the separately provisioned `PULLFROG_REMEDIATION_PUBLISH_TOKEN`, reloads the claim and sealed candidate, re-reads the PR identity, reapplies and re-guards the patch, creates one commit, re-reads the exact head immediately before a normal fast-forward push, and verifies the resulting PR head before recording a terminal receipt. Unlike a built-in-token push, this narrowly scoped publication credential emits the normal PR synchronize event so Pullfrog, CI, and Speculoos schedule fresh exact-head evidence without human workflow approval. The publish plan and terminal are mutually bound to the exact claim, candidate digest, patch digest, changed-path digest, source head, and resulting head.

Provider execution, trusted validation, and publication credentials therefore never coexist. Even if the native AddressReviews path attempts a reply, resolution, status, dispatch, approval, or push, the provider phase's job token cannot authorize it. The workflow cannot approve, merge, release, deploy, change settings, delete a branch, force-push, or use `force-with-lease`.

## Trigger and concurrency model

The dry-run workflow evaluates after:

- a completed Pullfrog check event;
- a completed configured CI or Speculoos workflow run;
- an explicit manual dispatch carrying an exact PR number and 40-character expected head SHA.

The concurrency key is repository plus expected head SHA. Runs for the same head are serialized rather than cancelled. Duplicate and superseding delivery safety comes from the exact-head claim contract, current-state re-read, app-bound latest-check selection, and completed-claim history input.

The hosted dry-run does not persist production claim history. The write-capable workflow persists single-record claim, candidate, and terminal artifacts plus separately retained transient dispatch and patch artifacts. It reconstructs only artifacts whose run belongs to the exact workflow path, validates every record against its claim, requires complete repository-artifact pagination, rejects expired matching records, and refuses PRs older than the 90-day durable-history window. It also requires every pushed terminal to match a stored candidate and sealed publish-plan digests, and derives a retryable failure only when a completed failed/cancelled/timed-out run proves that no publication occurred. An unresolved claim with possible head movement remains orphaned and blocks rather than guessing.

## Read-only collection

The coordinator performs bounded GitHub REST `GET` requests only. It reads:

1. repository default-branch metadata;
2. the PR before evidence collection;
3. Pullfrog reviews and review comments;
4. the PR file list;
5. exact-head check runs;
6. the PR again after collection.

The before and after PR identities must match. The triggering head, review head, and every required check head must equal the same current PR head.

Check names are accepted only from their configured GitHub App slugs. The `pullfrog` and `pullfrog-approval` checks must come from the `pullfrog` app and share one check suite. A same-named check from another app is counted as spoofed and ignored. When an allowed app has rerun a check, only its newest exact-head check is authoritative and earlier runs are counted as superseded.

## Required evidence

The current repository template requires:

- `pullfrog` from the Pullfrog app;
- `pullfrog-approval` from the same Pullfrog check suite;
- `dogfood / Provider-free PR automation contract` from GitHub Actions as CI evidence;
- `speculoos` from GitHub Actions as independent policy evidence;
- a successful local destination-guard decision over the current PR identity and changed-path set.

Missing, pending, failed, skipped, cancelled, timed-out, stale, malformed, wrong-app, or inconsistent evidence stops the decision. The required names and allowed apps are intentionally explicit and must be changed through reviewed workflow source, not an untrusted event or PR field.

## Sanitized evidence

Raw review bodies and comments are processed in memory and are never copied into the receipt or artifact. The receipt contains:

- repository, PR, ref, and SHA identity;
- check IDs, app slugs, statuses, and superseded/spoofed counts;
- finding fingerprints and output digests;
- changed-path count and digest, plus only the names of paths that violate the forbidden-path policy;
- destination-guard and cycle-contract decisions;
- explicit all-false mutation flags.

The workflow uploads only `artifacts/pullfrog-cloud-coordinator/receipt.json` with a 30-day retention period. It does not upload the raw GitHub snapshot.

## Fail-closed states

The coordinator stops on all cycle-contract and destination-guard failures, including:

- repository, PR, base, head, destination, or event drift;
- fork, detached ref, protected/default/base destination, or forbidden authority path;
- stale or missing Pullfrog review;
- missing, pending, failed, skipped, cancelled, or timed-out CI or Speculoos evidence;
- wrong-app check spoofing or Pullfrog check-suite mismatch;
- duplicate, malformed, or incomplete history;
- unchanged or reused heads;
- repeated finding sets or unchanged structured output;
- more than three remediation cycles.

A stopped receipt is uploaded first, then the workflow exits nonzero so failure remains visible without losing evidence.

## Activation boundary

Dry-run publication and the local write-capable implementation do not authorize remediation. Before the write-capable workflow is published to an active serving ref or manually dispatched, a separate exact-SHA approval and hosted acceptance must prove:

1. exact-head event, review, CI, Speculoos, and destination binding;
2. durable claim-history recovery and duplicate delivery handling;
3. pre-remediation and post-patch destination-guard enforcement;
4. separate approval and provisioning of `PULLFROG_REMEDIATION_PUBLISH_TOKEN` with only the same-repository feature-branch publication authority needed to emit normal revalidation events;
5. one bounded Pullfrog remediation pilot on an explicitly authorized same-repository feature head;
6. fresh Pullfrog review and independent checks after the produced commit;
7. stop behavior for no progress, repeated findings, failed/cancelled/timed-out evidence, head/base drift, forbidden paths, and cycle exhaustion.

Pullfrog approval and native repository-wide auto-merge remain disabled. The remediation job forces Pullfrog to reuse a built-in token with read-only content and pull-request permissions and no checks or actions write permission, while `authorPermission: none` withholds the gh CLI token, forces push off, and locks cross-run learnings. Its best-effort post-fix approval, thread, comment, status, and redispatch paths therefore cannot mutate repository-hosted state.

A separate repository-owned `auto_merge_eligible` job owns automatic merge. It runs only after the coordinator reports a clean exact-head result, then independently revalidates the sanitized receipt, same-repository identity, approved feature-head prefix, a valid base other than `main` or `master`, live base/head SHAs, all five trusted evidence checks, the latest exact-head Pullfrog review, the destination guard, and the absence of an unresolved human changes-requested review. Immediately before mutation it refreshes the app-bound Pullfrog, approval, CI, and Speculoos check runs so a newer same-head pending or failed result supersedes the earlier receipt.

The job does not use GitHub's pull-request merge endpoint because that endpoint can predicate only on the head SHA. Instead it fetches the literal reviewed base ref and PR head, builds a two-parent merge commit, and submits one normal fast-forward Git receive-pack update to the literal reviewed base ref. The update command carries the exact reviewed base SHA as its old OID, so the server rejects any concurrent base movement in the same ref transaction; PR retargeting cannot redirect the literal ref update. Force and force-with-lease are prohibited. The job explicitly rejects `main` and `master`, does not delete the source branch, has no provider or publisher credential, and is the only job with the built-in token's merge authority. Those two stable-branch merges remain human-authorized.

GitHub suppresses ordinary workflow events caused by a built-in-token push. For merges into `dev`, the gate reads the PR file list before merging and uses bounded `workflow_dispatch` calls afterward only when the same path filters would have selected the cross-repository workflow updater or reusable-workflow ref synchronizer. The dispatch inputs bind the old base SHA and confirmed merge SHA. Other eligible bases do not dispatch `dev` publication automation. A dispatch failure is recorded as `merged_with_downstream_failure` and fails the job after persisting the merge receipt, because the merge itself is already irreversible.

## Local validation

```bash
python3 -m unittest scripts/github/tests/test_pullfrog_cloud_coordinator.py -v
python3 -m unittest scripts/github/tests/test_pullfrog_cloud_coordinator_workflow_policy.py -v
python3 -m unittest scripts/github/tests/test_pullfrog_cloud_remediation.py -v
python3 -m unittest scripts/github/tests/test_pullfrog_dev_auto_merge.py -v
python3 -m unittest scripts/github/tests/test_pullfrog_cloud_remediation_workflow_policy.py -v
python3 -m py_compile \
  scripts/github/pullfrog_cloud_coordinator.py \
  scripts/github/pullfrog_cloud_remediation.py \
  scripts/github/pullfrog_dev_auto_merge.py \
  scripts/github/pullfrog_cycle_contract.py \
  scripts/github/pullfrog_destination_guard.py
scripts/github/validate_pullfrog_workflow.sh
```
