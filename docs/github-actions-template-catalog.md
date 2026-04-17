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
| CodeRabbit PR automation | Reusable | `templates/reusable-workflows/coderabbit-pr-automation.yml` | `.github/workflows/coderabbit-pr-automation.yml` | Shared remediation engine for CodeRabbit PR review issues |
| CodeRabbit PR automation (PR trigger) | Starter | `templates/starter-workflows/coderabbit-pr-automation-pr-trigger.yml` | none in this repo | Consumer-facing PR-event entrypoint wired to the reusable engine |
| CodeRabbit PR automation (manual trigger) | Starter | `templates/starter-workflows/coderabbit-pr-automation-manual-trigger.yml` | none in this repo | Consumer-facing manual-dispatch entrypoint wired to the reusable engine |
| CodeRabbit PR comment trigger | Starter | `templates/starter-workflows/coderabbit-pr-comment-trigger.yml` | none in this repo | Consumer-facing comment-triggered entrypoint that resolves PR context, then calls the reusable engine |
| Sync starter-workflow template refs (reusable) | Reusable | `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml` | `.github/workflows/sync-starter-workflow-template-refs-reusable.yml` | Deterministic maintenance workflow that materializes local workflow copies and syncs pinned reusable-workflow refs |
| Cross-repo workflow updater (reusable) | Reusable | `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml` | `.github/workflows/cross-repo-workflow-updater-reusable.yml` | Shared engine that clones consumer repos, renders starter-template updates, and opens consumer PRs |
| Sync starter-workflow template refs (trigger) | Starter | `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml` | `.github/workflows/sync-starter-workflow-template-refs-trigger.yml` | Repo-local trigger surface that calls the reusable maintenance workflow on push or manual dispatch |
| Cross-repo workflow updater (trigger) | Starter | `templates/starter-workflows/cross-repo-workflow-updater-trigger.yml` | `.github/workflows/cross-repo-workflow-updater-trigger.yml` | Repo-local trigger surface that calls the reusable cross-repo updater on push or manual dispatch |

## Asset details

---

## 1. CodeRabbit PR automation

- **Type:** reusable workflow
- **Canonical source:** `templates/reusable-workflows/coderabbit-pr-automation.yml`
- **Published call shape:** `fr-meyer/agent-toolkit/.github/workflows/coderabbit-pr-automation.yml@<sha>`
- **Live/runtime copy in this repo:** `.github/workflows/coderabbit-pr-automation.yml`
- **Governed by:**
  - ref-sync source in `templates/workflow-ref-sync-manifest.json`
- **Purpose:**
  - fetch CodeRabbit PR review-thread data
  - normalize actionable issues
  - prepare an agent runtime
  - run bounded remediation against a target repository
  - optionally validate, commit, and push the result

### When to use
Use this as the shared engine when a repository wants AI-assisted remediation for CodeRabbit PR comments or review threads.

### Main inputs
- PR and remediation controls:
  - `pr_number`
  - `run_validation`
  - `working_tree_must_be_clean`
  - `max_cycles`
- checkout/source controls:
  - `target_checkout_path`
  - `shared_checkout_path`
  - `shared_repository`
  - `shared_repository_ref`
- agent runtime controls:
  - `agent_runtime`
  - `agent_command_json`
  - `agent_command`
  - `cursor_cli`
  - `coderabbit_cli`
- shared-context installation controls:
  - `install_shared_skills`
  - `install_cursor_rules`
  - `shared_skills_install_mode`
- post-remediation Git controls:
  - `auto_commit`
  - `auto_push`
  - `commit_strategy`
  - `commit_count_mode`
  - `fixed_commit_count`
  - `stop_on_ambiguous_remainder`

### Secrets expected
- required:
  - `GH_TOKEN`
- optional:
  - `CURSOR_API_KEY`
  - `CODERABBIT_API_KEY`
  - `WORKFLOW_PUSH_TOKEN`

### Side effects
- checks out the consumer repo and the shared repo
- writes CodeRabbit artifacts under the target checkout
- may install shared skills or Cursor rules into the target repo
- may create and push remediation commits when enabled

### Notes
- This is the main reusable engine behind the three CodeRabbit starter workflows below.
- The paired `shared_repository_ref` should stay aligned with the pinned `uses: ...@<sha>` ref in calling templates when present.

---

## 2. CodeRabbit PR automation (PR trigger)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/coderabbit-pr-automation-pr-trigger.yml`
- **Live/runtime copy in this repo:** none currently materialized
- **Governed by:**
  - target in `templates/workflow-ref-sync-manifest.json`
- **Purpose:**
  - provide a consumer-facing entrypoint that runs the reusable CodeRabbit automation workflow on PR events

### When to use
Use this when a consumer repository wants automatic remediation on PR open, synchronize, or reopen events without hand-writing the reusable-workflow wiring.

### Trigger shape
- `pull_request` on `opened`, `synchronize`, `reopened`

### Consumer setup expected
Repository or organization variables may include:
- `CODERABBIT_RUNNER_LABELS_JSON`
- `CODERABBIT_AGENT_RUNTIME`
- `CODERABBIT_AGENT_COMMAND_JSON` or `CODERABBIT_AGENT_COMMAND`
- `CODERABBIT_CLI`
- `CURSOR_CLI`
- `CODERABBIT_INSTALL_SHARED_SKILLS`
- `CODERABBIT_INSTALL_CURSOR_RULES`
- `CODERABBIT_SHARED_SKILLS_INSTALL_MODE`
- `CODERABBIT_AUTO_COMMIT`
- `CODERABBIT_AUTO_PUSH`
- `CODERABBIT_COMMIT_STRATEGY`
- `CODERABBIT_COMMIT_COUNT_MODE`
- `CODERABBIT_FIXED_COMMIT_COUNT`
- `CODERABBIT_STOP_ON_AMBIGUOUS_REMAINDER`

Secrets may include:
- `CURSOR_API_KEY`
- `CODERABBIT_API_KEY`
- `WORKFLOW_PUSH_TOKEN`

### Calls
- `fr-meyer/agent-toolkit/.github/workflows/coderabbit-pr-automation.yml@<sha>`

### Notes
- This is a starter template, not a runtime workflow in this repo.
- It should remain thin and consumer-facing, with heavy logic kept in the reusable workflow.

---

## 3. CodeRabbit PR automation (manual trigger)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/coderabbit-pr-automation-manual-trigger.yml`
- **Live/runtime copy in this repo:** none currently materialized
- **Governed by:**
  - target in `templates/workflow-ref-sync-manifest.json`
- **Purpose:**
  - provide a consumer-facing manual-dispatch entrypoint that runs the reusable CodeRabbit automation workflow for a chosen PR number

### When to use
Use this when a consumer repository wants an explicit Run workflow button for CodeRabbit remediation without mixing that trigger surface into PR-event runs.

### Trigger shape
- `workflow_dispatch`

### Consumer setup expected
Repository or organization variables may include:
- `CODERABBIT_RUNNER_LABELS_JSON`
- `CODERABBIT_AGENT_RUNTIME`
- `CODERABBIT_AGENT_COMMAND_JSON` or `CODERABBIT_AGENT_COMMAND`
- `CODERABBIT_CLI`
- `CURSOR_CLI`
- `CODERABBIT_INSTALL_SHARED_SKILLS`
- `CODERABBIT_INSTALL_CURSOR_RULES`
- `CODERABBIT_SHARED_SKILLS_INSTALL_MODE`
- `CODERABBIT_AUTO_COMMIT`
- `CODERABBIT_AUTO_PUSH`
- `CODERABBIT_COMMIT_STRATEGY`
- `CODERABBIT_COMMIT_COUNT_MODE`
- `CODERABBIT_FIXED_COMMIT_COUNT`
- `CODERABBIT_STOP_ON_AMBIGUOUS_REMAINDER`

Secrets may include:
- `CURSOR_API_KEY`
- `CODERABBIT_API_KEY`
- `WORKFLOW_PUSH_TOKEN`

### Calls
- `fr-meyer/agent-toolkit/.github/workflows/coderabbit-pr-automation.yml@<sha>`

### Notes
- This is a starter template, not a runtime workflow in this repo.
- It should remain thin and consumer-facing, with heavy logic kept in the reusable workflow.

---

## 4. CodeRabbit PR comment trigger

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/coderabbit-pr-comment-trigger.yml`
- **Live/runtime copy in this repo:** none currently materialized
- **Governed by:**
  - target in `templates/workflow-ref-sync-manifest.json`
- **Purpose:**
  - react to CodeRabbit-authored PR comments, review comments, or review summaries
  - resolve the PR number and reject fork cases
  - call the shared CodeRabbit remediation engine only when the context is eligible

### When to use
Use this when a consumer repository wants remediation to start from CodeRabbit comment activity rather than directly from PR open/sync events.

### Trigger shape
- `issue_comment` created
- `pull_request_review_comment` created
- `pull_request_review` submitted

### Special behavior
- intentionally scoped to CodeRabbit-authored comments only
- resolves PR context in a separate job before calling the reusable workflow
- ignores review-summary events when the same review already contains inline review comments, to avoid duplicate runs
- skips fork-based cases

### Calls
- `fr-meyer/agent-toolkit/.github/workflows/coderabbit-pr-automation.yml@<sha>`

### Consumer setup expected
Uses the same general variable and secret model as the split PR and manual trigger starters.

---

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
- required:
  - `GH_TOKEN`

### Side effects
- clones consumer repositories into a local workspace directory
- may create updater branches in consumer repos
- may open reviewable PRs in consumer repos
- may post or update a managed divergence-review comment on the opened PR
- uploads the updater summary artifact and local consumer clone workspace

### Notes
- This reusable engine is intentionally separate from the trigger wrapper so the repo-local workflow layout stays aligned with the source-library model.
- The trigger wrapper for this engine lives in `templates/starter-workflows/cross-repo-workflow-updater-trigger.yml`.

---

## 8. Cross-repo workflow updater (trigger)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/cross-repo-workflow-updater-trigger.yml`
- **Live/runtime copy in this repo:** `.github/workflows/cross-repo-workflow-updater-trigger.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - provide the repo-local trigger surface that invokes the reusable cross-repo updater on push or manual dispatch

### When to use
Use this as the repository entrypoint that reacts to starter-template changes in the shared library and dispatches the reusable updater engine.

### Trigger shape
- `push` on `dev` for changes under:
  - `templates/starter-workflows/**`
  - `templates/cross-repo-workflow-distribution-manifest.json`
  - `scripts/github/cross_repo_workflow_updater.py`
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
- This asset keeps the repo-local automation pathway reusable as a canonical template plus a materialized live copy.
- Default divergence delivery is a managed PR comment on the update PR. Legacy committed review docs are fallback-only behavior.

## Live runtime copies in this repo

These files exist under `.github/workflows/` and should not be treated as the primary authoring location:
- `.github/workflows/coderabbit-pr-automation.yml`
- `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
- `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`
- `.github/workflows/cross-repo-workflow-updater-reusable.yml`
- `.github/workflows/cross-repo-workflow-updater-trigger.yml`

Their canonical sources are:
- `templates/reusable-workflows/coderabbit-pr-automation.yml`
- `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml`
- `templates/starter-workflows/cross-repo-workflow-updater-trigger.yml`

## Maintenance rule for this catalog

When adding, renaming, or materially changing a workflow asset:
1. update the canonical source under `templates/`
2. update the relevant manifest(s)
3. update this catalog so humans and agents can quickly understand the asset
4. re-materialize and validate any linked live runtime copies
