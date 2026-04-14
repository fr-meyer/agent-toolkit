# Workflow asset-library layout rules

## Core rule

Every live workflow under `.github/workflows/` should have a canonical source under `templates/`.

Live `.github/workflows/` files are runtime copies, not the preferred authoring location.

## Classification rule

Classify by role:

- `templates/reusable-workflows/` for callable reusable workflows, typically with `on: workflow_call`
- `templates/starter-workflows/` for copy/adapt entrypoints and starter templates

A repo-local trigger workflow can still belong in `templates/starter-workflows/` if its canonical role is an entrypoint template that may be copied or adapted later.

## Edit checklist

1. Confirm the repo really uses this source-library layout.
2. Read repo-local docs first if they exist.
3. Decide the workflow role before changing paths.
4. Edit the canonical source under `templates/`.
5. Update `templates/repo-workflow-materialization-manifest.json` if a live `.github/workflows/` copy is affected.
6. Update `templates/workflow-ref-sync-manifest.json` if starter-template pinned refs are affected.
7. Re-materialize live `.github/workflows/` copies.
8. Verify live copies match their canonical sources.
9. Update docs and agent guidance if the rule or architecture changed.

## Common mistakes

- treating `.github/workflows/` as the only source of truth
- creating a third category without a real role distinction
- classifying by execution location instead of workflow role
- renaming a canonical source without updating manifests and callers
- leaving a live workflow without a canonical template source
