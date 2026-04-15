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
| CodeRabbit PR automation wrapper | Starter | `templates/starter-workflows/coderabbit-pr-automation-wrapper.yml` | none in this repo | Consumer-facing PR automation entrypoint wired to the reusable engine |
| CodeRabbit PR comment trigger | Starter | `templates/starter-workflows/coderabbit-pr-comment-trigger.yml` | none in this repo | Consumer-facing comment-triggered entrypoint that resolves PR context, then calls the reusable engine |
| Sync starter-workflow template refs (reusable) | Reusable | `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml` | `.github/workflows/sync-starter-workflow-template-refs-reusable.yml` | Deterministic maintenance workflow that materializes local workflow copies and syncs pinned reusable-workflow refs |
| Sync starter-workflow template refs (trigger) | Starter | `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml` | `.github/workflows/sync-starter-workflow-template-refs-trigger.yml` | Repo-local trigger surface that calls the reusable maintenance workflow on push or manual dispatch |

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
- This is the main reusable engine behind the two CodeRabbit starter workflows below.
- The paired `shared_repository_ref` should stay aligned with the pinned `uses: ...@<sha>` ref in calling templates when present.

---

## 2. CodeRabbit PR automation wrapper

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/coderabbit-pr-automation-wrapper.yml`
- **Live/runtime copy in this repo:** none currently materialized
- **Governed by:**
  - target in `templates/workflow-ref-sync-manifest.json`
- **Purpose:**
  - provide a consumer-facing entrypoint that runs the reusable CodeRabbit automation workflow on PR events or manual dispatch

### When to use
Use this when a consumer repository wants a standard CodeRabbit PR remediation entrypoint without hand-writing the reusable-workflow wiring.

### Trigger shape
- `workflow_dispatch`
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

## 3. CodeRabbit PR comment trigger

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/coderabbit-pr-comment-trigger.yml`
- **Live/runtime copy in this repo:** none currently materialized
- **Governed by:**
  - target in `templates/workflow-ref-sync-manifest.json`
- **Purpose:**
  - react to CodeRabbit-authored PR comments or review comments
  - resolve the PR number and reject fork cases
  - call the shared CodeRabbit remediation engine only when the context is eligible

### When to use
Use this when a consumer repository wants remediation to start from CodeRabbit comment activity rather than directly from PR open/sync events.

### Trigger shape
- `issue_comment` created
- `pull_request_review_comment` created

### Special behavior
- intentionally scoped to CodeRabbit-authored comments only
- resolves PR context in a separate job before calling the reusable workflow
- skips fork-based cases

### Calls
- `fr-meyer/agent-toolkit/.github/workflows/coderabbit-pr-automation.yml@<sha>`

### Consumer setup expected
Uses the same general variable and secret model as the automation wrapper.

---

## 4. Sync starter-workflow template refs (reusable)

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

## 5. Sync starter-workflow template refs (trigger)

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
- `push` on `main` for changes under `templates/reusable-workflows/`
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

## Live runtime copies in this repo

These files exist under `.github/workflows/` and should not be treated as the primary authoring location:
- `.github/workflows/coderabbit-pr-automation.yml`
- `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
- `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`

Their canonical sources are:
- `templates/reusable-workflows/coderabbit-pr-automation.yml`
- `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`

## Maintenance rule for this catalog

When adding, renaming, or materially changing a workflow asset:
1. update the canonical source under `templates/`
2. update the relevant manifest(s)
3. update this catalog so humans and agents can quickly understand the asset
4. re-materialize and validate any linked live runtime copies
