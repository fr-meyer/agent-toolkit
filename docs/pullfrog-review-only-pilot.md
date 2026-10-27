# Pullfrog review and bounded-remediation gate

Pullfrog is the active primary reviewer for `fr-meyer/agent-toolkit`. A pull request cannot satisfy the repository review policy until both Pullfrog checks are successful on its current exact head:

- `pullfrog`: the bounded Pullfrog run completed successfully
- `pullfrog-approval`: Pullfrog has no outstanding review feedback for that exact commit

Pullfrog does not submit GitHub approvals, fix CI, merge, release, or deploy. A collaborator may explicitly start **Fix all** or **Fix 👍s** to let Pullfrog implement selected findings on the current PR branch. Every resulting head is re-reviewed from scratch for gate purposes, and Speculoos plus explicit human authority still control every merge.

## Default-branch bootstrap

PR #93 added the original non-pushing `.github/workflows/pullfrog.yml` to the default branch without promoting unrelated `dev` history. This cutover prepares the restricted-push version on `dev`, but does not alter the active default-branch copy. A separate minimal `main` bootstrap PR, explicit merge approval, and live `push: restricted` readback are required before any fix action can publish a commit. The workflow is also maintained canonically on `dev`:

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
- Pullfrog `push: restricted`, which blocks default-branch, tag, and branch-deletion pushes
- service-side pre-push allowlist limited to `feat/*`, `fix/*`, `docs/*`, `test/*`, and `chore/*`; this also blocks direct pushes to integration branch `dev`
- Pullfrog `shell: restricted`
- action timeout of 15 minutes inside a 20-minute job timeout
- workflow progress updates disabled

Live repository settings additionally enforce:

- automatic agent review with incremental re-review
- review model selector `openai/gpt-sol` with `--effort=xhigh`
- review-remediation model selector `openai/gpt-luna` with `--effort=xhigh`
- `pullfrog` and `pullfrog-approval` checks enabled
- manual **Fix all** and **Fix 👍s** remediation allowed only after an explicit collaborator action
- progress comments, review approval, automatic Address reviews, CI autofix, mentions, issue automation, label automation, and auto-merge disabled
- non-collaborator and draft reviews disabled
- environment allowlist unset/empty

The provider-free validator `scripts/github/validate_pullfrog_workflow.sh` checksum-verifies actionlint, validates both workflow copies, and runs deterministic assertions for triggers, permissions, immutable action refs, checkout credentials, timeouts, restricted push, restricted shell, disabled progress comments, and secret/environment mapping variants.

## Role-specific model and effort controls

Pullfrog reads built-in flags from each automation's custom instructions. The live repository configuration uses these exact role prompts:

- `prompts.review`: `--model=openai/gpt-sol --effort=xhigh`
- `prompts.address-reviews`: `--model=openai/gpt-luna --effort=xhigh` plus the bounded-remediation instructions

Pullfrog prompt flags take supported model selectors, not provider wire identifiers. In pinned Pullfrog `v0.1.102`, `openai/gpt-sol` resolves to `openai/gpt-6.1-sol` and `openai/gpt-luna` resolves to `openai/gpt-6-luna`; both catalog entries publish `xhigh`. Repository-level `effort` is a numeric default from `0` to `1`; the named per-role `--effort=xhigh` flags take precedence for these runs.

`address-reviews.enabled` stays false. That switch controls unattended handling of human reviews on Pullfrog-opened PRs; it is not needed for the explicit **Fix all** and **Fix 👍s** actions used here.

## Exact-head evidence rule

For every pull request:

1. Record the PR number, base, head branch, and full head SHA.
2. Read the live `pullfrog` and `pullfrog-approval` checks for that exact SHA.
3. Read the Pullfrog review thread and retain its URLs as evidence.
4. After every remediation or other head update, re-run the gate; older checks or reviews are stale.
5. Require live GitHub checks and Speculoos validation independently.
6. Merge only after a separate explicit human decision through the branch-policy merge actor.

A failed, cancelled, missing, or stale Pullfrog check blocks normal closeout. Mergeguez review evidence is historical only and cannot substitute for either Pullfrog check.

## Publication boundary

The repository stores no credential, provider token, billing state, prompt transcript, or raw model output. Pullfrog may publish commits only to a policy-approved PR branch after an explicit fix action. It cannot approve or merge. The Mergeguez broker remains a transport and explicitly authorized merge mechanism only; it is no longer the review authority.
