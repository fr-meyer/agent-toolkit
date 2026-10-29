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
| CodeRabbit PR comment trigger | Starter | `templates/starter-workflows/coderabbit-pr-comment-trigger.yml` | `.github/workflows/coderabbit-pr-comment-trigger.yml` | Repo-local and consumer-facing comment-triggered entrypoint that resolves PR context, then calls the reusable engine |
| Repository similarity preflight CI | Starter | `templates/starter-workflows/repository-similarity-preflight-ci.yml` | `.github/workflows/repository-similarity-preflight-ci.yml` | Repo-local validation entrypoint for the repository-similarity-preflight skill |
| Sync starter-workflow template refs (reusable) | Reusable | `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml` | `.github/workflows/sync-starter-workflow-template-refs-reusable.yml` | Deterministic maintenance workflow that materializes local workflow copies and syncs pinned reusable-workflow refs |
| Cross-repo workflow updater (reusable) | Reusable | `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml` | `.github/workflows/cross-repo-workflow-updater-reusable.yml` | Shared engine that clones consumer repos, renders starter-template updates, and opens consumer PRs |
| Sync starter-workflow template refs (trigger) | Starter | `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml` | `.github/workflows/sync-starter-workflow-template-refs-trigger.yml` | Repo-local trigger surface that calls the reusable maintenance workflow on push or manual dispatch |
| Cross-repo workflow updater (push trigger) | Starter | `templates/starter-workflows/cross-repo-workflow-updater-push-trigger.yml` | `.github/workflows/cross-repo-workflow-updater-push-trigger.yml` | Repo-local push entrypoint that calls the reusable cross-repo updater when shared starter assets change |
| Cross-repo workflow updater (manual trigger) | Starter | `templates/starter-workflows/cross-repo-workflow-updater-manual-trigger.yml` | `.github/workflows/cross-repo-workflow-updater-manual-trigger.yml` | Repo-local manual-dispatch entrypoint that calls the reusable cross-repo updater without an irrelevant skipped sibling job |
| PR automation dogfood (reusable) | Reusable | `templates/reusable-workflows/pr-automation-dogfood-reusable.yml` | `.github/workflows/pr-automation-dogfood-reusable.yml` | Provider-free contract runner for exact-head evidence, actor separation, bounded cycles, and human-only merge readiness |
| PR automation dogfood (PR trigger) | Starter | `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml` | `.github/workflows/pr-automation-dogfood-pr-trigger.yml` | Read-only PR entrypoint for changes to the dogfood harness and its workflow assets |
| Pullfrog review entrypoint | Starter | `templates/starter-workflows/pullfrog.yml` | `.github/workflows/pullfrog.yml` | Bounded, non-pushing Pullfrog entrypoint retained while unattended remediation stays approval-gated |
| Pullfrog cloud coordinator (dry run) | Starter | `templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml` | `.github/workflows/pullfrog-cloud-coordinator-dry-run.yml` | Provider-free exact-head state-machine evaluator with read-only GitHub collection and sanitized receipts |
| Speculoos PR gate | Starter | `templates/starter-workflows/speculoos.yml` | `.github/workflows/speculoos.yml` | Read-only exact-head Speculoos policy and publication-contract evidence for non-stable PRs |

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
- built-in by default:
  - `GITHUB_TOKEN`
- optional:
  - `CURSOR_API_KEY`
  - `CODERABBIT_API_KEY`
  - `ELEVATED_GITHUB_TOKEN` when default GitHub permissions are not enough

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
- **Live/runtime copy in this repo:** none in this repo
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
- `ELEVATED_GITHUB_TOKEN` when default GitHub permissions are not enough

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
- `ELEVATED_GITHUB_TOKEN` when default GitHub permissions are not enough

### Calls
- `fr-meyer/agent-toolkit/.github/workflows/coderabbit-pr-automation.yml@<sha>`

### Notes
- This is a starter template, not a runtime workflow in this repo.
- It should remain thin and consumer-facing, with heavy logic kept in the reusable workflow.

---

## 4. CodeRabbit PR comment trigger

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/coderabbit-pr-comment-trigger.yml`
- **Live/runtime copy in this repo:** `.github/workflows/coderabbit-pr-comment-trigger.yml`
- **Governed by:**
  - target in `templates/workflow-ref-sync-manifest.json`
  - target in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - react to CodeRabbit-authored PR comments, review comments, or review summaries
  - resolve the PR number and reject fork cases
  - call the shared CodeRabbit remediation engine only when the context is eligible

### When to use
Use this when a consumer repository or this repository itself wants remediation to start from CodeRabbit comment activity rather than directly from PR open/sync events.

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

### Notes
- This starter is now materialized as a live repo-local workflow in `.github/workflows/`.
- Keep the live copy aligned through both the materialization manifest and the ref-sync manifest.

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

---

## 10. Repository similarity preflight CI

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/repository-similarity-preflight-ci.yml`
- **Live/runtime copy in this repo:** `.github/workflows/repository-similarity-preflight-ci.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - run the repository-similarity-preflight unit tests
  - compile the Python helper
  - validate the Agent Skill package
  - reject whitespace errors in pull-request or manual-dispatch checks

### When to use
Use this as the repo-local validation entrypoint when the repository-similarity-preflight skill or its CI definition changes.

### Trigger shape
- `pull_request` for changes under:
  - `skills/repository-similarity-preflight/**`
  - `templates/starter-workflows/repository-similarity-preflight-ci.yml`
  - `.github/workflows/repository-similarity-preflight-ci.yml`
- `workflow_dispatch`

### Notes
- This is a standalone CI entrypoint rather than a callable `workflow_call` engine, so its canonical source belongs under `templates/starter-workflows/`.
- It does not call an in-repo reusable workflow and therefore does not need a `templates/workflow-ref-sync-manifest.json` binding.

## 11. PR automation dogfood (reusable)

- **Type:** reusable workflow
- **Canonical source:** `templates/reusable-workflows/pr-automation-dogfood-reusable.yml`
- **Live/runtime copy in this repo:** `.github/workflows/pr-automation-dogfood-reusable.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - run the focused provider-free contract tests
  - evaluate deterministic positive and fail-closed fixtures
  - prove exact-head evidence, actor separation, claim idempotency, bounded cycles, required checks, and human-only merge readiness

### Security boundary
- `contents: read` only
- checkout credentials are not persisted
- no provider or secret inputs
- no GitHub mutation, commit, push, review, merge, deployment, or release

### Notes
- A successful receipt is `ready_for_human_merge`, never an approval or merge operation.
- The same-commit PR trigger calls this workflow with a relative path, so no pinned reusable-workflow ref diffusion is needed.
- See `docs/pr-automation-dogfood.md` for the fixture and receipt contract.

---

## 12. PR automation dogfood (PR trigger)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml`
- **Live/runtime copy in this repo:** `.github/workflows/pr-automation-dogfood-pr-trigger.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - run the dogfood harness on pull requests to any non-stable base except `main` or `master` when its evaluator, fixtures, workflow assets, manifest, or documentation changes

### Calls
- `./.github/workflows/pr-automation-dogfood-reusable.yml`

### Notes
- The entrypoint is intentionally thin.
- Its ordered base filter includes nested branch names, then excludes `main` and `master`, so every base eligible for repository-owned auto-merge can produce the required CI evidence while stable-branch PRs stay outside automatic merge authority.
- Its path filter keeps unrelated repository changes from creating a dogfood run.

---

## 13. Pullfrog review entrypoint

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/pullfrog.yml`
- **Live/runtime copy in this repo:** `.github/workflows/pullfrog.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - provide the workflow-dispatch surface expected by the Pullfrog GitHub App
  - keep Pullfrog review execution bounded and non-pushing while write-capable activation remains separately gated
  - preserve immutable action custody for the sole intended AI reviewer and future fixer

### Security boundary
- top-level `contents: read`
- job-level `id-token: write` and `contents: read`
- checkout credentials are not persisted
- Pullfrog `model: openai/gpt-sol` and `effort: xhigh`
- Pullfrog `push: disabled`
- Pullfrog `shell: restricted`
- no provider-key or other secret environment mapping
- 15-minute action timeout inside a 20-minute job timeout

### Notes
- The target architecture uses Pullfrog as the sole AI reviewer and intended fixer. The committed entrypoint still disables pushes, so this change does not activate remediation.
- Mergeguez retains the separately approved publication/manual-merge broker role and is not a reviewer in the target architecture. Pullfrog-native auto-merge stays disabled; the remediation workflow's separate exact-head gate may auto-merge eligible feature PRs into any valid base except `main` or `master`, while those stable branches remain human-authorized.
- Repository-side configuration and model access are separate, approval-gated surfaces and are not stored in this public workflow.
- This standalone entrypoint does not call a reusable workflow, so it needs no reusable-workflow ref diffusion.
- See `docs/pullfrog-review-only-pilot.md` for historical pilot evidence and `docs/pullfrog-cloud-coordinator.md` for the current automation architecture.

---

## 14. Pullfrog cloud coordinator (dry run)

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml`
- **Live/runtime copy in this repo:** `.github/workflows/pullfrog-cloud-coordinator-dry-run.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - collect bounded exact-head Pullfrog, CI, and Speculoos evidence through GitHub REST `GET` requests
  - evaluate the destination guard and three-cycle contract
  - serialize same-head evidence events through a concurrency group
  - upload one sanitized receipt before failing closed when evidence is incomplete or unsafe

### Security boundary
- `checks: read`, `contents: read`, and `pull-requests: read` only
- checkout, setup-python, and artifact actions pinned to immutable commits
- no provider action, provider secret, elevated token, commit, push, approval, merge, rerun, release, deployment, settings change, or branch deletion
- raw reviews, comments, and PR snapshots are never uploaded
- any `start_remediation` result is reported only as `would_action`; `executed_action` stays `none`

### Notes
- Automatic evidence triggers cover Pullfrog check completion plus configured CI/Speculoos workflow completion; manual dispatch requires an exact PR number and head SHA.
- The live template names one required CI check and one Speculoos check, both bound to the `github-actions` app. Wrong-app lookalikes are ignored.
- This dry-run surface does not persist production claim history or invoke remediation. Hosted history recovery, post-patch guard enforcement, and one bounded write pilot remain separate gates.
- See `docs/pullfrog-cloud-coordinator.md` for the state machine, receipt contract, and activation boundary.

---

## 15. Pullfrog review-model fallback

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/pullfrog-review-fallback.yml`
- **Live/runtime copy in this repo:** `.github/workflows/pullfrog-review-fallback.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - recognize only the two literal apostrophe variants of the recorded Sol cybersecurity-policy refusal
  - authorize at most one `openai/gpt-astra` / `xhigh` Pullfrog review for an unchanged exact PR head and base
  - emit the composite exact-head `pullfrog-review-gate` without treating a failed raw primary check as clean
  - keep review evidence separate from remediation, publication, approval, merge, settings, and required-check authority

### Security boundary
- inert unless `PULLFROG_REVIEW_FALLBACK_ENABLED` is exactly `true` or a manual dispatch authorizes one exact check/PR/head/base identity
- evaluator has read-only Actions, checks, contents, and PR access
- provider job has Pullfrog OIDC plus read-only job permissions; the sealed controller mints one short-lived Pullfrog App lease scoped exactly to `contents: read` plus `pull_requests: write`, forces it through the action's external `GH_TOKEN` route, and revokes it after result capture, preventing the action from minting its normal content/issue/check/action-write MCP token
- provider execution is allowed only on `github.run_attempt == 1` and the trusted preflight repeats that check; failed-job reruns skip Astra while retaining the ability to rerun trusted finalization against the first attempt's bounded artifact
- fresh finalizer has read access plus check-write but no provider identity, content-write, approval, dispatch, publication, or merge credential
- exactly one failed `Run review-only agent` step and exactly one literal matching failure annotation are required; extra failed steps, annotations, or wording variation fail closed
- structured result and sanitized token lease/revocation receipts are size-bounded, and the exact-head review, Astra footer, finding count, comment actor, comment head, exact token scope, and successful revocation are revalidated before gate success

### Notes
- Sol and Astra are both OpenAI models, so this is not independent cross-provider evidence. A second refusal or any other failure stops without a third model.
- Source availability is not activation authority. Default-branch placement, credential-route audit, one hosted pilot, composite-gate consumer integration, required-check migration, and rollout remain separate gates.
- See `docs/pullfrog-review-model-fallback.md` for the incident evidence, controller contract, and rollout sequence.

---

## 16. Pullfrog cloud remediation loop

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/pullfrog-cloud-remediation-loop.yml`
- **Live/runtime copy in this repo:** `.github/workflows/pullfrog-cloud-remediation-loop.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - run native Pullfrog `fix_review` remediation without giving the provider a repository write token
  - persist exact-head claims before execution and reconstruct bounded retry/cycle history from trusted workflow artifacts
  - treat provider output as untrusted, rebuild and seal it in a fresh read-only validation job, then publish it through a separate trusted compare-and-swap job
  - let each successful commit trigger fresh Pullfrog, CI, and Speculoos evidence for the next bounded cycle
  - automatically merge a clean exact-head same-repository feature PR into any valid base except `main` or `master`, preserving the repository's merge-commit convention

### Security boundary
- provider job: `id-token: write` for provider routing, `contents: read`, `pull-requests: read`, and the built-in read token mapped as `GH_TOKEN` so Pullfrog cannot mint its normal write-capable MCP token; Pullfrog also uses `push: disabled`, restricted shell, `authorPermission: none` to withhold gh and learning writes, and no provider-secret mapping
- validator job: read-only permissions, a fresh trusted controller checkout, and a fresh exact-source checkout; it alone converts the untrusted provider bundle into a canonical digest-bound candidate
- publisher job: one separately provisioned `PULLFROG_REMEDIATION_PUBLISH_TOKEN`, no provider identity token, and one normal fast-forward push to the exact same-repository PR head; unlike `github.token`, this push emits the PR synchronize event that schedules fresh Pullfrog, CI, and Speculoos evidence
- auto-merge job: built-in token limited to `actions: write`, `checks: read`, `contents: write`, and `pull-requests: write`, no provider identity or publisher secret, and one normal fast-forward Git receive-pack update of a two-parent merge commit only after refreshing clean app-bound evidence and live base identity; the update command carries the exact reviewed base SHA as its old OID, so the server rejects concurrent base advancement in the same ref-update transaction and concurrent retargeting cannot redirect the literal ref update; only merges into `dev` replay path-matched `dev` push automation that built-in-token events suppress
- the durable claim artifact contains only `claim.json`, while the sealed dispatch is a separate transient artifact; claim, candidate, publish plan, patch, changed paths, source/result heads, and pushed terminal evidence are schema-validated and mutually digest-bound
- forks, protected/default/base refs, stale or reused heads, workflow/governance paths, malformed history, repeated findings, unchanged output, and no-progress states fail closed
- no force-push, approval, Pullfrog-native auto-merge, merge into `main` or `master`, release, deployment, settings change, branch deletion, or elevated token

### Notes
- Pullfrog `v0.1.102` receives the native dispatch envelope through the exact `prompt` input. `prompt_file` is deliberately not used because Pullfrog treats it as plain text and would discard the `fix_review` event contract.
- The full artifact ledger and its nested coordinator history are emitted separately. Enumeration must be complete, matching expired records fail closed, and PRs outside the 90-day durable-history window are not eligible for unattended remediation.
- Hosted activation additionally requires separate approval and provisioning of the publisher-only `PULLFROG_REMEDIATION_PUBLISH_TOKEN`; no credential value is stored in this repository.
- Source availability is not activation authority. Publishing the exact local commit, activating the workflow on a serving ref, and running the first hosted write pilot each remain separately gated.
- See `docs/pullfrog-cloud-coordinator.md` for the credential split, ledger recovery rules, cycle contract, and hosted acceptance boundary.

---

## 17. Speculoos PR gate

- **Type:** starter workflow
- **Canonical source:** `templates/starter-workflows/speculoos.yml`
- **Live/runtime copy in this repo:** `.github/workflows/speculoos.yml`
- **Governed by:**
  - source in `templates/repo-workflow-materialization-manifest.json`
- **Purpose:**
  - emit the exact `speculoos` GitHub Actions check required by the Pullfrog coordinator
  - bind the current manifest task to the exact PR head branch, head SHA, base branch, and base SHA
  - run the repository-bound Speculoos contract validator against the exact PR diff and publication packet
  - run the checksum-verified Pullfrog workflow validation surface independently from the controller

### Security boundary
- runs only for PR bases other than exactly `main` or `master`
- checks out the exact PR head with persisted credentials disabled
- uses only `contents: read` and never receives provider, publisher, elevated, approval, or merge credentials
- executes only repository-reviewed source from `scripts/github/speculoos_pr_contract.py`; it does not fetch the private Speculoos repository or require a cross-repository token
- validates exact changed-file inventory, release wording, documentation impact, workflow materialization, merge actor policy, whitespace, and red-list token patterns
- uploads only the generated validation reports, retained for 90 days

### Notes
- The job name is deliberately exactly `speculoos`; the coordinator rejects wrong-name or wrong-app lookalikes.
- The task contract must identify the live PR branch and base. Missing, stale, unsafe, or mismatched task metadata fails closed.
- The local official Speculoos CLI remains the authoring-time validator and publication-packet checker. The hosted job uses the narrower repository-bound contract so the public repository does not need credentials for the private Speculoos source repository.
- The repository records `dev` explicitly while the independent custom merge controller remains authoritative for the broader any-valid-base-except-`main`/`master` policy.

## Live runtime copies in this repo

These files exist under `.github/workflows/` and should not be treated as the primary authoring location:
- `.github/workflows/coderabbit-pr-automation.yml`
- `.github/workflows/coderabbit-pr-comment-trigger.yml`
- `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
- `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`
- `.github/workflows/cross-repo-workflow-updater-reusable.yml`
- `.github/workflows/cross-repo-workflow-updater-push-trigger.yml`
- `.github/workflows/cross-repo-workflow-updater-manual-trigger.yml`
- `.github/workflows/repository-similarity-preflight-ci.yml`
- `.github/workflows/pr-automation-dogfood-reusable.yml`
- `.github/workflows/pr-automation-dogfood-pr-trigger.yml`
- `.github/workflows/pullfrog.yml`
- `.github/workflows/pullfrog-cloud-coordinator-dry-run.yml`
- `.github/workflows/pullfrog-review-fallback.yml`
- `.github/workflows/pullfrog-cloud-remediation-loop.yml`
- `.github/workflows/speculoos.yml`

Their canonical sources are:
- `templates/reusable-workflows/coderabbit-pr-automation.yml`
- `templates/starter-workflows/coderabbit-pr-comment-trigger.yml`
- `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml`
- `templates/starter-workflows/cross-repo-workflow-updater-push-trigger.yml`
- `templates/starter-workflows/cross-repo-workflow-updater-manual-trigger.yml`
- `templates/starter-workflows/repository-similarity-preflight-ci.yml`
- `templates/reusable-workflows/pr-automation-dogfood-reusable.yml`
- `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml`
- `templates/starter-workflows/pullfrog.yml`
- `templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml`
- `templates/starter-workflows/pullfrog-review-fallback.yml`
- `templates/starter-workflows/pullfrog-cloud-remediation-loop.yml`
- `templates/starter-workflows/speculoos.yml`

## Maintenance rule for this catalog

When adding, renaming, or materially changing a workflow asset:
1. update the canonical source under `templates/`
2. update the relevant manifest(s)
3. update this catalog so humans and agents can quickly understand the asset
4. re-materialize and validate any linked live runtime copies
