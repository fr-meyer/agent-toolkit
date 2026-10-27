# Pullfrog review-only gate

Pullfrog is the active primary reviewer for `fr-meyer/agent-toolkit`. A pull request cannot satisfy the repository review policy until both Pullfrog checks are successful on its current exact head:

- `pullfrog`: the bounded Pullfrog run completed successfully
- `pullfrog-approval`: Pullfrog has no outstanding review feedback for that exact commit

Pullfrog does not submit GitHub approvals, push commits, implement review feedback, fix CI, merge, release, or deploy. Speculoos still validates repository policy and explicit human authority still controls every merge.

## Default-branch bootstrap

PR #93 added the non-pushing `.github/workflows/pullfrog.yml` to the default branch without promoting unrelated `dev` history. This cutover keeps that fail-closed publication boundary and maintains the workflow canonically on `dev`:

- Canonical source: `templates/starter-workflows/pullfrog.yml`
- Live materialized copy on `dev`: `.github/workflows/pullfrog.yml`
- Materialization binding: `templates/repo-workflow-materialization-manifest.json`
- Pullfrog action: immutable commit `25a837a2b078177c3acdce790506d1fd1acedd82`, reviewed as Pullfrog `v0.1.102`
- Checkout action: immutable commit `d23441a48e516b6c34aea4fa41551a30e30af803`, tagged `v6`
- Workflow syntax: actionlint `1.7.12`, verified against SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`

The default-branch copy is the dispatch surface used by the Pullfrog GitHub App. Feature PRs continue to target `dev`; release/promotion PRs target `main` and remain separately approval-gated.

## Enforced workflow boundary

The committed workflow enforces:

- top-level `contents: read`
- job-level `id-token: write` and `contents: read`
- no provider-key, secret expression, or environment mapping
- checkout credentials not persisted
- Pullfrog `push: disabled`
- Pullfrog `shell: restricted`
- action timeout of 15 minutes inside a 20-minute job timeout
- workflow progress updates disabled

Repository policy requires the following service controls, with the active review model independently confirmed by the current Pullfrog review output:

- automatic agent review with incremental re-review
- review model selector `openai/gpt-sol` with `--effort=xhigh`
- `pullfrog` and `pullfrog-approval` checks enabled
- progress comments, review approval, review remediation, automatic Address reviews, CI autofix, mentions, issue automation, label automation, and auto-merge disabled
- non-collaborator and draft reviews disabled
- environment allowlist unset/empty

The provider-free validator `scripts/github/validate_pullfrog_workflow.sh` checksum-verifies actionlint, validates both workflow copies, and runs deterministic assertions for triggers, permissions, immutable action refs, checkout credentials, timeouts, disabled push, restricted shell, disabled progress comments, and secret/environment mapping variants.

## Role-specific model and effort controls

Pullfrog reads built-in flags from each automation's custom instructions. The active review path uses this exact prompt:

- `prompts.review`: `--model=openai/gpt-sol --effort=xhigh`

The current exact-head Pullfrog review reports `gpt-6.1-sol`, matching pinned Pullfrog `v0.1.102` resolution of `openai/gpt-sol`. `openai/gpt-luna` at `xhigh`, resolving to `openai/gpt-6-luna`, remains the selected but inactive policy target for any future remediation path; it is not accepted as live routing evidence while remediation is disabled.

## Remediation stop gate

Pinned Pullfrog `v0.1.102` increments a pre-push failure counter when its service-side hook rejects a destination, then skips that hook on subsequent push attempts in the same run. Its built-in `restricted` mode blocks the default branch, tags, and deletion, but does not enforce this repository's narrower branch-prefix allowlist. The hook is therefore not a fail-closed authorization boundary.

`address-reviews.enabled` stays false, workflow push stays disabled, and the review's **Fix all** and **Fix 👍s** links must not be triggered. Remediation may be reconsidered only after all of these are true:

1. A verified server-side rule or non-bypassable runtime guard enforces the allowed destination branches.
2. Tests reject a forbidden destination on the first push attempt and again after a hook failure and retry.
3. Tests permit an approved feature branch destination.
4. Re-enablement receives separate explicit authorization.

## Exact-head evidence rule

For every pull request:

1. Record the PR number, base, head branch, and full head SHA.
2. Read the live `pullfrog` and `pullfrog-approval` checks for that exact SHA.
3. Read the Pullfrog review thread and retain its URLs as evidence.
4. Re-run the gate after every head update; older checks or reviews are stale.
5. Require live GitHub checks and Speculoos validation independently.
6. Merge only after a separate explicit human decision through the branch-policy merge actor.

A failed, cancelled, missing, or stale Pullfrog check blocks normal closeout. Mergeguez review evidence is historical only and cannot substitute for either Pullfrog check.

## Publication boundary

The repository stores no credential, provider token, billing state, prompt transcript, or raw model output. Pullfrog cannot publish code or merge. The Mergeguez broker remains a transport and explicitly authorized merge mechanism only; it is no longer the review authority.
