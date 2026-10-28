# Pullfrog exact-head cycle contract

This contract is the provider-free decision core for the unattended Pullfrog review, remediation, and re-review loop.

It does not call Pullfrog, GitHub, Git, or a model. It accepts one bounded JSON observation and returns a deterministic decision. The later GitHub Actions coordinator may act only when the decision is `remediation_ready` with action `start_remediation`.

## Decisions

- `clean` / `complete`: the exact head has a successful Pullfrog review with no findings, all required evidence is current and successful, and `pullfrog-approval` is successful.
- `remediation_ready` / `start_remediation`: the exact head has normalized findings, all non-approval evidence is current and successful, `pullfrog-approval` is failing consistently with outstanding findings, the destination guard passed, progress is visible, and the next cycle remains within the configured maximum of three.
- `duplicate` / `none`: the exact claim was already consumed. Duplicate delivery is idempotent and performs no action.
- `stopped` / `none`: any identity, evidence, history, progress, or cycle invariant failed.

## Exact-head compare-and-swap

The input carries separate `expected` and `observed` repository identities. Repository slug, PR number, base ref/SHA, head ref/SHA, and head-repository slug must all match. Event, review, and required-check evidence must also carry the same observed head SHA.

Any drift stops the cycle. A remediation commit therefore creates a new head that requires an entirely fresh review and fresh checks before another decision can be reached.

## Required evidence

Every decision requires exact-head results for:

- `pullfrog`
- `pullfrog-approval`
- `ci`
- `speculoos`
- `destination-guard`

`pullfrog`, `ci`, `speculoos`, and `destination-guard` must succeed. `pullfrog-approval` must succeed for a clean review and fail for a review with outstanding findings. Missing, pending, failed, cancelled, timed-out, skipped, malformed, duplicated, or stale evidence stops the cycle unless that failure is the expected approval result for outstanding findings.

## Bounded progress and idempotency

The claim key is `owner/repository:pr-number:head-sha:cycle-number`. Completed claims are idempotent and cannot trigger another remediation run.

Cycle history records the remediation source head, normalized finding-set digest, and structured output digest for each completed remediation. The evaluator stops on:

- more than three remediation cycles;
- an unchanged or reused head;
- an incomplete or malformed history;
- repeated normalized findings;
- unchanged structured output.

The receipt contains hashes and counts, not raw finding summaries or arbitrary input notes.

## Local validation

```bash
python3 -m unittest scripts/github/tests/test_pullfrog_cycle_contract.py -v
python3 -m py_compile scripts/github/pullfrog_cycle_contract.py scripts/github/tests/test_pullfrog_cycle_contract.py
```

## Activation boundary

This contract authorizes no repository write by itself. Write-capable remediation remains disabled until the destination guard, dry-run coordinator, hosted exact-head acceptance matrix, and separately authorized remediation pilot pass.
