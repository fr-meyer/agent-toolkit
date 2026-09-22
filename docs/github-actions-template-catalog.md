# GitHub Actions template catalog

This document is the human-readable catalog of the workflow assets stored in this repository.

Use it when you need to answer questions like:
- what workflow templates exist here
- what each one is for
- whether it is a reusable workflow or a starter workflow
- which live `.github/workflows/` file it materializes to, if any
- which manifests govern it
- what inputs, secrets, variables, and follow-up expectations apply

For exact source-to-target bindings, also consult:
- `templates/repo-workflow-materialization-manifest.json`
- `templates/workflow-ref-sync-manifest.json`

## Reading guide

### Asset types
- **Reusable workflow**: canonical callable workflow source under `templates/reusable-workflows/`
- **Starter workflow**: canonical entrypoint/template source under `templates/starter-workflows/`
- **Live runtime copy**: materialized `.github/workflows/` file used by this repository at runtime

### Source-of-truth rule
- Canonical workflow authoring happens under `templates/`
- `.github/workflows/` contains live runtime copies only
- Every live workflow should have a canonical source under `templates/`

## Inventory summary

| Name | Type | Canonical source | Live/runtime copy | Primary purpose |
| --- | --- | --- | --- | --- |
| Sync starter-workflow template refs (reusable) | Reusable | `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml` | `.github/workflows/sync-starter-workflow-template-refs-reusable.yml` | Deterministic maintenance workflow that materializes local workflow copies and syncs pinned reusable-workflow refs |
| Cross-repo workflow updater (reusable) | Reusable | `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml` | `.github/workflows/cross-repo-workflow-updater-reusable.yml` | Shared engine that clones consumer repos, renders starter-template updates, and opens consumer PRs |
| Sync starter-workflow template refs (trigger) | Starter | `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml` | `.github/workflows/sync-starter-workflow-template-refs-trigger.yml` | Repo-local trigger surface that calls the reusable maintenance workflow on push or manual dispatch |
| Cross-repo workflow updater (push trigger) | Starter | `templates/starter-workflows/cross-repo-workflow-updater-push-trigger.yml` | `.github/workflows/cross-repo-workflow-updater-push-trigger.yml` | Repo-local push entrypoint that calls the reusable cross-repo updater when shared starter assets change |
| Cross-repo workflow updater (manual trigger) | Starter | `templates/starter-workflows/cross-repo-workflow-updater-manual-trigger.yml` | `.github/workflows/cross-repo-workflow-updater-manual-trigger.yml` | Repo-local manual-dispatch entrypoint that calls the reusable cross-repo updater without an irrelevant skipped sibling job |

## Asset details

---

CodeRabbit remediation workflow assets are retired. Mergeguez review is
requested through the approved broker/comment protocol, while Speculoos consumes
exact-head evidence through `review-evidence` and `merge-plan`; no GitHub Actions
workflow in this catalog invokes a reviewer or performs remediation.

## 5. Sync starter-workflow template refs (reusable)

- **Type:** reusable workflow
- **Canonical source:** `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- **Live/runtime copy in this repo:** `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
- **Governed by:**
  - source in `templates/workflow-ref-sync-manifest.json`
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - materialize repo-local workflow copies from canonical templates
  - detect changed reusable workflows
  - prepare bounded ref-sync context
  - update pinned reusable-workflow refs in mapped target files
  - validate the updates
  - optionally commit and push workflow-asset maintenance changes

### When to use
Use this as the maintenance engine that keeps starter templates and linked live workflows aligned with the authoritative reusable workflow commit.

### Main inputs
- `before_sha`
- `after_sha`
- `auto_commit`
- `auto_push`
- `python_version`
- `triggered_by_push`

### Side effects
- materializes `.github/workflows/` files from canonical templates
- writes temporary sync context under `.tmp/reusable-workflow-ref-sync/`
- may update pinned `uses: ...@<sha>` refs in managed targets
- may commit and push workflow-asset maintenance changes
- uploads `.tmp/reusable-workflow-ref-sync` as a workflow artifact during runs

### Notes
- This is the core maintenance workflow that fixed the recent stale-pin issue in the trigger workflow.
- It enforces allowed file-scope changes during maintenance.

---

## 6. Sync starter-workflow template refs (trigger)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- **Live/runtime copy in this repo:** `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`
- **Governed by:**
  - target in `templates/workflow-ref-sync-manifest.json`
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - provide the repo-local trigger surface for running the reusable maintenance workflow
  - ensure the trigger itself stays pinned to the correct reusable-workflow commit

### When to use
Use this as the repo entrypoint that invokes maintenance whenever reusable workflow sources change, or when a human manually dispatches the maintenance workflow.

### Trigger shape
- `push` on `dev` for changes under `templates/reusable-workflows/`
- `workflow_dispatch`

### Calls
- `fr-meyer/agent-toolkit/.github/workflows/sync-starter-workflow-template-refs-reusable.yml@<sha>`

### Main dispatch inputs
- `before_sha`
- `after_sha`
- `auto_commit`
- `auto_push`
- `python_version`

### Notes
- The trigger and the reusable maintenance workflow are intentionally separate.
- The trigger is itself managed by the same pinned-ref maintenance model it invokes.
- When maintenance produces a diff, it creates a dedicated workflow-sync branch from `dev` and opens or reuses a PR for that branch.

---

## 7. Cross-repo workflow updater (reusable)

- **Type:** reusable workflow
- **Canonical source:** `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml`
- **Live/runtime copy in this repo:** `.github/workflows/cross-repo-workflow-updater-reusable.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - clone managed consumer repositories locally
  - run the shared cross-repo updater script
  - open reviewable PRs into consumer repos when shared starter templates change
  - upload a machine-readable updater summary artifact

### When to use
Use this as the shared engine for distributing starter-workflow updates from this repository into registered consumer repositories.

### Main inputs
- `source_commit`
- `previous_source_commit`
- `create_pr`
- `dry_run`
- `manual_review_on_divergence`
- `manual_review_delivery`
- `include_normalization_patch`
- `branch_prefix`
- `consumer_local_root`
- `python_version`
- `consumer_filter`
- `starter_template_filter`

### Secrets expected
- built-in by default:
  - `GITHUB_TOKEN`
- optional when cross-repo or other elevated GitHub operations need more rights than the default token:
  - `ELEVATED_GITHUB_TOKEN`

### Side effects
- clones consumer repositories into a local workspace directory
- may create updater branches in consumer repos
- may open reviewable PRs in consumer repos
- may post or update a managed divergence-review comment on the opened PR
- uploads the updater summary artifact and local consumer clone workspace

### Notes
- This reusable engine is intentionally separate from the trigger wrapper so the repo-local workflow layout stays aligned with the source-library model.
- The repo-local entrypoint wrappers for this engine live in `templates/starter-workflows/cross-repo-workflow-updater-push-trigger.yml` and `templates/starter-workflows/cross-repo-workflow-updater-manual-trigger.yml`.

---

## 8. Cross-repo workflow updater (push trigger)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/cross-repo-workflow-updater-push-trigger.yml`
- **Live/runtime copy in this repo:** `.github/workflows/cross-repo-workflow-updater-push-trigger.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - provide the repo-local push trigger surface that invokes the reusable cross-repo updater when shared starter assets change

### When to use
Use this as the repository entrypoint that reacts automatically to starter-template changes in the shared library and dispatches the reusable updater engine without an irrelevant skipped manual sibling job.

### Trigger shape
- `push` on `dev` for changes under:
  - `templates/starter-workflows/**`
  - `templates/cross-repo-workflow-distribution-manifest.json`
  - `scripts/github/cross_repo_workflow_updater.py`

### Calls
- `./.github/workflows/cross-repo-workflow-updater-reusable.yml`

### Notes
- The trigger and reusable updater are intentionally separated.
- This asset keeps the repo-local automation pathway reusable as a canonical template plus a materialized live copy.
- Default divergence delivery is a managed PR comment on the update PR. Legacy committed review docs are fallback-only behavior.

---

## 9. Cross-repo workflow updater (manual trigger)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/cross-repo-workflow-updater-manual-trigger.yml`
- **Live/runtime copy in this repo:** `.github/workflows/cross-repo-workflow-updater-manual-trigger.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - provide the repo-local manual-dispatch trigger surface that invokes the reusable cross-repo updater for ad hoc runs

### When to use
Use this when you want an explicit Run workflow button for the cross-repo updater without carrying a permanently skipped push sibling job in the same run.

### Trigger shape
- `workflow_dispatch`

### Calls
- `./.github/workflows/cross-repo-workflow-updater-reusable.yml`

### Main dispatch inputs
- `source_commit`
- `previous_source_commit`
- `create_pr`
- `dry_run`
- `manual_review_on_divergence`
- `manual_review_delivery`
- `include_normalization_patch`
- `branch_prefix`
- `consumer_local_root`
- `python_version`
- `consumer_filter`
- `starter_template_filter`

### Notes
- The trigger and reusable updater are intentionally separated.
- This asset exists separately from the push trigger to keep the Actions UI clean and avoid irrelevant skipped sibling jobs.
- Default divergence delivery is a managed PR comment on the update PR. Legacy committed review docs are fallback-only behavior.

## Live runtime copies in this repo

These files exist under `.github/workflows/` and should not be treated as the primary authoring location:
- `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
- `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`
- `.github/workflows/cross-repo-workflow-updater-reusable.yml`
- `.github/workflows/cross-repo-workflow-updater-push-trigger.yml`
- `.github/workflows/cross-repo-workflow-updater-manual-trigger.yml`

Their canonical sources are:
- `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml`
- `templates/starter-workflows/cross-repo-workflow-updater-push-trigger.yml`
- `templates/starter-workflows/cross-repo-workflow-updater-manual-trigger.yml`

## Maintenance rule for this catalog

When adding, renaming, or materially changing a workflow asset:
1. update the canonical source under `templates/`
2. update the relevant manifest(s)
3. update this catalog so humans and agents can quickly understand the asset
4. re-materialize and validate any linked live runtime copies
