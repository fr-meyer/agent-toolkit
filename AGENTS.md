# AGENTS.md

Repo-local instructions for humans and agents working in `shared-agent-skills`.

## Read this first when touching workflow assets

1. `README.md`
2. `docs/workflow-asset-library-layout.md`
3. `docs/workflow-authoring-rules.md`
4. `docs/repo-scope.md`

## Workflow rule summary

- Author workflow source files under `templates/`, not primarily under `.github/workflows/`.
- Classify by role:
  - callable reusable workflows -> `templates/reusable-workflows/`
  - copy/adapt entrypoints and starter templates -> `templates/starter-workflows/`
- Treat `.github/workflows/` as live rendered runtime copies.
- Every live workflow in `.github/workflows/` should have a canonical template source.

## Required follow-through when editing workflows

When a workflow asset changes:

1. update the canonical template source
2. update `templates/repo-workflow-materialization-manifest.json` if needed
3. update `templates/workflow-ref-sync-manifest.json` if starter-template pinned refs are affected
4. re-materialize `.github/workflows/` copies
5. update docs if the architecture or rule changed

## Intent

This repo is a shared workflow and skill library. Keep the structure stable, explicit, and easy for future agents to recover.
