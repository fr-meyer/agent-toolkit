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

## Trigger and concurrency model

The dry-run workflow evaluates after:

- a completed Pullfrog check event;
- a completed configured CI or Speculoos workflow run;
- an explicit manual dispatch carrying an exact PR number and 40-character expected head SHA.

The concurrency key is repository plus expected head SHA. Runs for the same head are serialized rather than cancelled. Duplicate and superseding delivery safety comes from the exact-head claim contract, current-state re-read, app-bound latest-check selection, and completed-claim history input.

The hosted dry-run does not yet persist production claim history. The deterministic evaluator accepts and validates that history so the hosted acceptance matrix can prove duplicate, repeated-finding, unchanged-output, unchanged-head, and three-cycle terminal behavior before mutation is enabled.

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

Dry-run publication does not authorize remediation. Before any write-capable workflow is enabled, a separate approval and hosted acceptance must prove:

1. exact-head event, review, CI, Speculoos, and destination binding;
2. durable claim-history recovery and duplicate delivery handling;
3. pre-remediation and post-patch destination-guard enforcement;
4. one bounded Pullfrog remediation pilot on an explicitly authorized same-repository feature head;
5. fresh Pullfrog review and independent checks after the produced commit;
6. stop behavior for no progress, repeated findings, failed/cancelled/timed-out evidence, head/base drift, forbidden paths, and cycle exhaustion.

Pullfrog approval and auto-merge remain disabled. Every merge remains separately human-authorized.

## Local validation

```bash
python3 -m unittest scripts/github/tests/test_pullfrog_cloud_coordinator.py -v
python3 -m unittest scripts/github/tests/test_pullfrog_cloud_coordinator_workflow_policy.py -v
python3 -m py_compile \
  scripts/github/pullfrog_cloud_coordinator.py \
  scripts/github/pullfrog_cycle_contract.py \
  scripts/github/pullfrog_destination_guard.py
scripts/github/validate_pullfrog_workflow.sh
```
