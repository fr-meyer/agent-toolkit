# Pullfrog review-model fallback audit and rollout

## Scope and current incident

This design handles one narrow failure mode in the Pullfrog review path: the
primary `openai/gpt-sol` review fails with the exact OpenAI cybersecurity-policy
refusal before Pullfrog produces a complete exact-head verdict.

The motivating PR #95 evidence was bound to:

- repository: `fr-meyer/agent-toolkit`;
- base: `dev` at `75418a1557b501b82c1ec0f7ee901a8dccaaacb7`;
- head: `56d4dde95e457c51cbcab3f9efee7f105f905552`;
- Pullfrog check run: `122715968993`;
- Pullfrog Actions run: `40658694176`;
- incomplete Pullfrog review: `5679976549`.

The Pullfrog job annotation contains one failure:

> action failed: provider error: This content was flagged for possible cybersecurity risk. If this seems wrong, try rephrasing your request. If you’re doing authorized security work that requires more cyber permissive safeguards, apply for Daybreak access via https://platform.openai.com/settings/organization/status-and-access before retrying.

Review `5679976549` has an empty summary body, so it is not a complete verdict.
It nevertheless left exact-head inline comment `4398558244`, reporting a
policy-test discovery bypass. That comment remains actionable and must not be
silently discarded. A fallback review must reconcile it. The partial comment
also demonstrates why a failed action cannot be treated as clean merely because
it created some GitHub review state.

The local implementation addresses that bypass by removing candidate-directory
`unittest discover` from the protected workflow validator. Each allowlisted
workflow-policy test is now executed directly with `python3 -I`, so an adjacent
candidate-controlled standard-library namesake such as `json.py` is not added to
the import path. A regression test proves the namesake is not imported, and the
destination-guard suite explicitly asserts that every fallback authority file is
protected. The hosted inline finding remains unresolved until this change is
published and Pullfrog re-reviews the resulting exact head.

## Model and action audit

The repository remains pinned to
`pullfrog/pullfrog@25a837a2b078177c3acdce790506d1fd1acedd82`
(`v0.1.102`). That action exposes per-run `model`, `effort`, `push`, `shell`,
`progress_comments`, and `output_schema` inputs.

At the pinned revision:

- `openai/gpt-sol` resolves to `openai/gpt-6.1-sol`;
- `openai/gpt-astra` resolves to `openai/gpt-6-astra`;
- both accept `xhigh` reasoning effort;
- no `gpt-6.1-astra`, Astra Pro, or Astra Mini alias is exposed;
- `openai/gpt-terra` resolves to `openai/gpt-5.6-terra`, not GPT 6.1 Terra.

The fallback therefore uses exactly:

```yaml
model: openai/gpt-astra
effort: xhigh
```

Astra and Sol are both OpenAI models. This fallback is not independent
cross-provider evidence and may encounter the same policy layer. If Astra
refuses or fails, the gate stops. There is no third model.

## Implemented local contract

The implementation is prepared but not activated:

- controller: `scripts/github/pullfrog_review_fallback.py`;
- canonical contract: `scripts/github/pullfrog_review_contract.py`;
- canonical workflow: `templates/starter-workflows/pullfrog-review-fallback.yml`;
- materialized workflow: `.github/workflows/pullfrog-review-fallback.yml`;
- tests: `scripts/github/tests/test_pullfrog_review_fallback.py` and
  `scripts/github/tests/test_pullfrog_review_fallback_workflow_policy.py`.

The primary `templates/starter-workflows/pullfrog.yml` now explicitly pins Sol
at `xhigh`; callers cannot select the fallback by changing an input.

The fallback controller:

1. accepts only a completed `pullfrog` check from the `pullfrog` GitHub App;
2. resolves the linked Actions run and requires the trusted
   `.github/workflows/pullfrog.yml` workflow, `workflow_dispatch`, and
   `pullfrog[bot]` actor;
3. re-reads the live same-repository open PR and current repository-owned
   trusted-author policy, then requires unchanged exact base/head repositories,
   refs, SHAs, author ID/login/type, policy schema/digest, and derived identity
   digest;
4. requires exactly one failed `Run review-only agent` step and no other
   failed step;
5. requires exactly one failure annotation whose text exactly equals one of
   the two explicit apostrophe variants of the recorded refusal;
6. rejects every additional failure annotation and every other failure cause;
7. rejects fallback when a complete exact-head Pullfrog verdict already exists;
8. records partial exact-head reviews/comments only as counts and digests, never
   as raw receipt text;
9. treats the composite gate bound to the complete identity digest, evidence
   profile, and evidence digest as the durable attempt claim, and rejects every
   fresh duplicate evaluation for that exact identity;
10. permits provider execution only on `github.run_attempt == 1`, with the same
    invariant rechecked by the trusted preflight, so failed-job and individual-job
    reruns cannot consume another Astra attempt;
11. allows a later workflow-run attempt to reuse the bounded first-attempt artifact
    only for trusted finalization recovery, never for provider execution;
12. authorizes one `openai/gpt-astra` / `xhigh` run and no recursive model chain.

A native complete verdict requires an exact-head Pullfrog review with a
nonempty body and Pullfrog's completion marker, trusted exact-head `pullfrog`
and `pullfrog-approval` checks from the Pullfrog App in one check suite, and no
unresolved Pullfrog review thread. A scoped fallback or Sol re-review instead
uses the `review-only` evidence profile because its short-lived token has no
check-write authority. The separate trusted publisher supplies the composite
gate only after it re-reads and matches the authoritative review ID and current
evidence digest. Inline comments attached to an empty-body, failed review remain
evidence to reconcile, but do not manufacture a complete verdict.

Every fallback result receipt, exact-head re-review receipt, reconciliation
record, gate publication, and controller handoff carries the same identity
digest. Each trusted transition reconstructs it from the live PR and current
repository-owned policy, so author or policy drift cannot inherit an earlier
review result or gate.

After a remediation commit, a finding-free Sol re-review may enter the explicit
`reconciliation_required` state when only prior `pullfrog[bot]` threads remain
open, even when the raw approval check is failed because those threads are still
open. A separate trusted job with no provider identity can resolve only those
bounded prior threads. It rejects current-review threads, human threads,
identity or evidence drift, genuine findings, and any non-thread blocker, then
re-reads the full contract and requires `clean` before the check-write-only
publisher can emit a successful digest-bound gate.

## Workflow and credential separation

Gate evaluation runs for every completed primary Pullfrog check so complete Sol
reviews can produce the repository-owned gate even while Astra is disabled.
Provider fallback execution remains inert unless either:

- repository variable `PULLFROG_REVIEW_FALLBACK_ENABLED` equals `true`; or
- a manual dispatch explicitly sets `authorize_fallback: true` and supplies the
  exact primary check, PR, head, and base identity.

Its jobs separate authority:

1. **Evaluate** has only Actions/check/content/PR read access.
2. **Publish initial gate** has check-write authority but no provider identity
   or content/PR write authority.
3. **Run fallback** has Pullfrog OIDC plus content/PR read access. Immediately
   before provider execution, the sealed trusted controller exchanges the runner
   OIDC assertion for one short-lived Pullfrog App installation token scoped
   exactly to `contents: read` and `pull_requests: write`. That lease is forced
   through the action's documented external `GH_TOKEN` route, so Pullfrog can
   publish its bot-authored review without minting its normal MCP token with
   content, issue, check, and action-dispatch write scopes. The provider still
   has no check, action-dispatch, content-write, approval, merge, or publication
   credential beyond the narrow review authority. Pullfrog is forced to
   `push: disabled`, `shell: restricted`, and a strict structured output schema.
   The lease is revoked after result capture, and both its exact scope receipt
   and successful revocation are required for a valid verdict.
4. **Finalize** has check-write plus read access, no provider identity, and no
   publication or merge credential. It accepts only a structured result whose
   repository, PR, head, base, model, effort, review ID, verdict, and finding
   count validate against fresh GitHub state and an exact-head Pullfrog review
   footer showing `gpt-6-astra`. Every associated finding comment must belong to
   Pullfrog, bind to that exact head, and match the structured count; a clean
   verdict must have zero comments.

Only bounded action outcome/result files and sanitized lease/revocation receipts
cross from the provider job to the trusted finalizer. No token value, patch,
provider credential, prompt, raw log, or content/check/action-dispatch write
token crosses the provider boundary. Failed-job reruns skip the entire provider
job via `github.run_attempt == 1`; when the first attempt already persisted its
bounded artifact, a later attempt may rerun only the fresh validator and gate
finalizer. The trusted default-branch finalizer alone has check-write plus
workflow-dispatch authority. After publishing, it re-reads the live open PR,
gate, contract status, evidence profile/digest, and expected conclusion before
one exact-PR/head controller handoff; in-progress, invalid, stale, drifted, or
digest-mismatched gates do not dispatch.

## Composite required check

The repository-owned check is `pullfrog-review-gate`. It uses a deterministic
external ID containing repository, PR number, exact base SHA, exact head SHA,
evidence profile, and evidence digest. The check is:

- successful for a valid clean complete Sol verdict;
- in progress while the one authorized Astra fallback runs;
- successful for a valid clean structured exact-head Astra verdict;
- failed with the matching review-only digest for valid findings that may enter
  bounded remediation but can never authorize merge;
- failed with a distinct non-canonical digest for every invalid state, including
  Astra refusal, malformed output, token-scope or revocation failure,
  review/model mismatch, drift, API failure, or duplicate attempt. That digest
  cannot match current canonical findings evidence or authorize remediation.

While Astra activation is disabled, a recognized refusal publishes
`action_required` and cannot invoke the fallback provider. Complete primary Sol
reviews are still evaluated and can publish a success gate.

Branch protection should eventually require `pullfrog-review-gate`, not the raw
`pullfrog` run-status check: the original Sol check remains failed after an
authorized successful Astra fallback. A native gate requires trusted
`pullfrog` plus `pullfrog-approval` evidence from one Pullfrog check suite. A
review-only gate requires a freshly reconstructed complete review and Pullfrog
thread contract from the scoped fallback or re-review. It does not remove the
separate destination guard, CI, Speculoos, human-review, and
Mergeguez/governance evidence.

## Remaining activation gates

Preparing this source does not authorize hosted execution, repository settings,
or merge. Activation requires separate approval for each of these stages:

1. publish the implementation through the approved App/Mergeguez lane;
2. place the trusted controller on the serving default branch without enabling
   the fallback variable;
3. confirm the scoped Pullfrog App lease can run Astra, authors the review as
   `pullfrog[bot]`, carries only `contents: read` plus `pull_requests: write`,
   revokes successfully, and exposes no content/check/action-dispatch or
   publication/merge credential;
4. manually pilot one exact PR/head/base with `authorize_fallback: true`;
5. prove Astra behavior, exact-head structured output, partial-comment
   reconciliation, one-attempt idempotency, fail-closed second refusal, and the
   live-revalidated explicit gate-to-controller handoff;
6. review and then enable `PULLFROG_REVIEW_FALLBACK_ENABLED`;
7. change branch protection to require `pullfrog-review-gate` and remove the raw
   primary `pullfrog` check only after hosted evidence proves the composite;
8. rerun destination, approval, CI, Speculoos, public-safety, secret, workflow
   identity, and exact-base checks before any automated merge.

PR #95 remains open and fail-closed until the unresolved inline finding and all
required exact-head evidence are reconciled. A valid digest-matched fallback
finding may authorize only the same bounded remediation path as a native
finding. It never directly authorizes publication, approval, or merge.

## Local verification

```bash
python3 -I -m py_compile scripts/github/pullfrog_review_fallback.py
python3 -I scripts/github/tests/test_pullfrog_review_fallback.py -v
python3 -I scripts/github/tests/test_pullfrog_review_fallback_workflow_policy.py -v
scripts/github/validate_pullfrog_workflow.sh
```
