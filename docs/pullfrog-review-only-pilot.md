# Pullfrog review gate

Pullfrog is the active primary reviewer for `fr-meyer/agent-toolkit`. A pull request cannot satisfy the repository review policy until both Pullfrog checks are successful on its current exact head:

- `pullfrog`: the bounded Pullfrog run completed successfully
- `pullfrog-approval`: Pullfrog has no outstanding review feedback for that exact commit

Pullfrog does not submit GitHub approvals, push commits, implement review feedback, fix CI, merge, release, or deploy. Speculoos still validates repository policy and explicit human authority still controls every merge.

## Default-branch bootstrap

PR #93 added `.github/workflows/pullfrog.yml` to the default branch without promoting unrelated `dev` history. The workflow is also maintained canonically on `dev`:

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

Live repository settings additionally enforce:

- automatic agent review with incremental re-review
- model `openai/gpt-sol` through the approved Codex subscription binding
- `pullfrog` and `pullfrog-approval` checks enabled
- progress comments, review approval, review remediation, CI autofix, mentions, issue automation, label automation, and auto-merge disabled
- non-collaborator and draft reviews disabled
- environment allowlist unset/empty

The provider-free validator `scripts/github/validate_pullfrog_workflow.sh` checksum-verifies actionlint, validates both workflow copies, and runs deterministic assertions for triggers, permissions, immutable action refs, checkout credentials, timeouts, disabled push, restricted shell, disabled progress comments, and secret/environment mapping variants.

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
