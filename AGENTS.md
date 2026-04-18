# AGENTS.md

Repo-local instructions for humans and agents working in `shared-agent-skills`.

## Read this first when touching workflow assets

1. `README.md`
2. `docs/github-actions-template-catalog.md`
3. `docs/workflow-asset-library-layout.md`
4. `docs/workflow-authoring-rules.md`
5. `docs/repo-scope.md`

## Workflow rule summary

- The fastest human/agent entrypoint for workflow discovery is `docs/github-actions-template-catalog.md`.
- Author workflow source files under `templates/`, not primarily under `.github/workflows/`.
- Classify by role:
  - callable reusable workflows -> `templates/reusable-workflows/`
  - copy/adapt entrypoints and starter templates -> `templates/starter-workflows/`
- Treat `.github/workflows/` as live rendered runtime copies.
- Prefer built-in `GITHUB_TOKEN` for default GitHub auth, and reserve `WORKFLOW_PUSH_TOKEN` for elevated or cross-repo auth.
- Every live workflow in `.github/workflows/` should have a canonical template source.
- `templates/repo-workflow-materialization-manifest.json` binds canonical template sources to their live `.github/workflows/` copies.
- `templates/workflow-ref-sync-manifest.json` binds reusable workflow sources to the starter and linked live workflow targets whose pinned `uses: ...@<sha>` refs should be diffused automatically.

## Required follow-through when editing workflows

When a workflow asset changes:

1. update the canonical template source
2. update `templates/repo-workflow-materialization-manifest.json` if any live `.github/workflows/` source or target path is added, removed, or renamed
3. decide whether the reusable workflow also needs SHA diffusion into starter templates, linked live workflows, or both
4. update `templates/workflow-ref-sync-manifest.json` whenever that source-to-target binding changes
5. re-materialize `.github/workflows/` copies
6. verify pinned `uses: ...@<sha>` refs still match the intended reusable workflow commit, and update `shared_repository_ref` too when that field exists
7. update docs if the architecture or rule changed

## Current automation policy

- Workflow-maintenance branches must be created from `dev`, not `main` or `master`.
- Repo-local workflow maintenance should land through a dedicated PR branch, not by pushing workflow-sync commits directly onto the triggering branch.
- Cross-repo divergence review should be delivered on the update PR as a managed PR comment by default.
- Legacy committed review artifacts under `docs/shared-workflow-reviews/` are transitional only and should not be the long-term review mechanism.

## Intent

This repo is a shared workflow and skill library. Keep the structure stable, explicit, and easy for future agents to recover.
