# Pullfrog review-only pilot

This repository carries a bounded Pullfrog entrypoint for an observational review pilot. Pullfrog is optional comparison evidence. It does not replace the required exact-head Mergeguez review, Speculoos policy checks, or explicit human merge authority.

## Workflow custody

- Canonical source: `templates/starter-workflows/pullfrog.yml`
- Live materialized copy: `.github/workflows/pullfrog.yml`
- Materialization binding: `templates/repo-workflow-materialization-manifest.json`
- Pullfrog action: immutable commit `25a837a2b078177c3acdce790506d1fd1acedd82`, reviewed as Pullfrog `v0.1.102`
- Checkout action: immutable commit `d23441a48e516b6c34aea4fa41551a30e30af803`, tagged `v6`
- Workflow syntax: actionlint `1.7.12`, downloaded from its versioned release and verified against SHA-256 `8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8`

The workflow uses only `workflow_dispatch`, which is also the dispatch surface used by the Pullfrog GitHub App. It becomes runnable only after the reviewed workflow reaches the repository default branch and Pullfrog is separately configured for the repository.

## Enforced workflow boundary

The committed workflow enforces:

- top-level `contents: read`
- job-level `id-token: write` and `contents: read`
- no provider-key or other secret environment mapping
- checkout credentials not persisted
- Pullfrog `push: disabled`
- Pullfrog `shell: restricted`
- action timeout of 15 minutes inside a 20-minute job timeout
- live progress updates disabled

The provider-free dogfood check runs `scripts/github/validate_pullfrog_workflow.sh`. It verifies the actionlint archive before execution, validates both workflow copies with actionlint, and runs deterministic assertions for the trigger, permissions, immutable action refs, checkout credentials, timeouts, disabled push, restricted shell, disabled progress comments, and absence of secret environment mappings.

Repository-side Pullfrog settings must additionally keep approval, auto-merge, review remediation, CI autofix, non-collaborator mentions, issue automation, and label automation disabled for the pilot. The environment allowlist stays empty. Those service settings are deliberately not represented as secrets or machine-local state in this public repository.

## Pilot evidence rule

For each pilot run:

1. Record the pull request number and exact head SHA before invocation.
2. Run one review-only request, without requesting file changes, pushes, approval, or merge.
3. Bind every Pullfrog check, review, comment, and Actions URL to that same head SHA.
4. Compare the result with independent Mergeguez and Speculoos evidence.
5. Treat Pullfrog output as optional comparison evidence only.
6. Do not merge through Pullfrog or because Pullfrog reports success.

Stop the pilot if the action pin changes, the reviewed PR head moves before invocation, model access is not explicitly authorized, or Pullfrog asks for broader shell, environment, push, approval, remediation, autofix, or merge authority.

## Non-goals

This workflow does not:

- store credentials or provider keys
- select or fund a model
- grant Pullfrog review approval authority
- permit commits or pushes
- address review comments or fix CI
- enable automatic reviews on all pull requests
- configure branch protection
- authorize or perform merges, releases, or deployments
