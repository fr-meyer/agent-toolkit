# Workflow asset-library layout rules

## Core rule

Every live workflow under `.github/workflows/` should have a canonical source under `templates/`.

Live `.github/workflows/` files are runtime copies, not the preferred authoring location.

## Token naming rule

Prefer built-in `GITHUB_TOKEN` for default GitHub auth.
Use `ELEVATED_GITHUB_TOKEN` only when extra GitHub rights are required.
Do not introduce ad hoc aliases for the default token when these two names already cover the need.

## Classification rule

Classify by role:

- `templates/reusable-workflows/` for callable reusable workflows, typically with `on: workflow_call`
- `templates/starter-workflows/` for copy/adapt entrypoints and starter templates

A repo-local trigger workflow can still belong in `templates/starter-workflows/` if its canonical role is an entrypoint template that may be copied or adapted later.

## Manifest responsibilities

- `templates/repo-workflow-materialization-manifest.json`
  - binds canonical template sources to live `.github/workflows/` copies
- `templates/workflow-ref-sync-manifest.json`
  - binds reusable workflow sources to the target files whose pinned `uses: ...@<sha>` refs should be diffused automatically

Ref-sync targets can include starter templates and linked live workflows.

## Edit checklist

1. Confirm the repo really uses this source-library layout.
2. Read repo-local docs first if they exist.
3. Decide the workflow role before changing paths.
4. Edit the canonical source under `templates/`.
5. Update `templates/repo-workflow-materialization-manifest.json` if a live `.github/workflows/` copy is affected.
6. Decide whether the reusable workflow needs SHA diffusion into starter templates only, or starter templates plus linked live workflows.
7. Update `templates/workflow-ref-sync-manifest.json` whenever that source-to-target binding changes.
8. Re-materialize live `.github/workflows/` copies.
9. Verify live copies match their canonical sources.
10. Verify pinned `uses: ...@<sha>` refs were updated correctly, and verify `shared_repository_ref` too when that field exists.
11. Update docs and agent guidance if the rule or architecture changed.

## Common mistakes

- treating `.github/workflows/` as the only source of truth
- creating a third category without a real role distinction
- classifying by execution location instead of workflow role
- renaming a canonical source without updating manifests and callers
- forgetting that materialization and SHA diffusion are controlled by two different manifests
- introducing workflow-specific token aliases when `GITHUB_TOKEN` or `ELEVATED_GITHUB_TOKEN` already cover the auth boundary
- leaving a reusable workflow unbound in the ref-sync manifest when its SHA should be diffused into starter or linked live targets
- leaving a live workflow without a canonical template source
