# Cross-repo workflow distribution concrete spec

Status: draft concrete spec

Related concept draft:
- `docs/cross-repo-workflow-distribution.md`
- `docs/cross-repo-workflow-updater-contract.md`

## 1. Purpose

This spec defines the first concrete implementation for distributing shared GitHub workflow assets from this repository into consumer repositories.

It formalizes the currently preferred **Option B** model:
- this repo remains the canonical source library
- consumer repos keep their own live `.github/workflows/` files
- upstream workflow updates propagate through **reviewable pull requests**, not silent direct pushes

## 2. Canonical model

### Shared repo roles

- `templates/reusable-workflows/` = shared engines
- `templates/starter-workflows/` = portable wrapper templates for consumer repos
- `.github/workflows/` in this repo = local runtime and dogfooding copies

### Consumer repo role

A consumer repo owns:
- its live `.github/workflows/` files
- its vars, secrets, and environment-specific configuration
- its merge decision for any incoming workflow update PR

## 3. Design constraints

- Environment-specific values must not be hardcoded into managed live workflow files unless explicitly unavoidable and documented.
- Shared logic should live in reusable workflows whenever possible.
- Consumer-facing live workflows should remain thin wrappers around shared reusable workflows.
- Cross-repo updates must be reviewable, bounded, and reversible.
- V1 must prefer correctness and safety over maximum automation.

## 4. V1 scope

V1 supports:
- a shared-repo registry of consumer repos
- managed distribution of selected starter workflows into selected consumer repos
- PR-based updates only
- exact file replacement for managed consumer workflow files
- reusable-workflow SHA bumps when those bumps are reflected in canonical starter templates
- validation before PR creation

V1 does not support:
- direct auto-merge into consumer default branches
- arbitrary three-way merging of consumer-local edits inside managed workflow files
- partial line-level patching of consumer workflow files
- automatic rollback commits after merge

## 5. Dependency on the existing in-repo model

This cross-repo updater depends on the shared repo already being internally consistent.

Expected sequence:
1. a reusable workflow changes in `templates/reusable-workflows/`
2. the shared repo's existing ref-sync/materialization automation converges the shared repo itself
3. canonical starter templates under `templates/starter-workflows/` now reflect the correct pinned reusable-workflow refs
4. the cross-repo updater distributes those starter-template changes to consumer repos

Important consequence:
- the cross-repo updater should treat **starter templates as the consumable canonical source** for consumer live workflows
- reusable workflow changes matter cross-repo when they result in starter-template changes, especially pinned SHA changes

## 6. Registry file

V1 introduces a dedicated registry file:
- `templates/cross-repo-workflow-distribution-manifest.json`

Its purpose is to declare:
- which consumer repos are managed
- which starter templates are installed in each consumer repo
- where each managed target file lives in the consumer repo
- what divergence policy applies

## 7. Registry schema

Proposed V1 shape:

```json
{
  "schemaVersion": "1.0.0",
  "sharedRepository": "fr-meyer/agent-toolkit",
  "sourceBranch": "main",
  "consumers": [
    {
      "repo": "owner/example-repo",
      "updateMode": "pull_request",
      "managedBindings": [
        {
          "starterTemplate": "templates/starter-workflows/coderabbit-pr-comment-trigger.yml",
          "targetPath": ".github/workflows/coderabbit-pr-comment-trigger.yml",
          "divergencePolicy": "exact",
          "enabled": true,
          "notes": "Consumer must provide required vars/secrets documented by the starter template."
        }
      ]
    }
  ]
}
```

## 8. Registry rules

- `starterTemplate` must point to a canonical source file under `templates/starter-workflows/`.
- `targetPath` must point to a workflow file under `.github/workflows/` in the consumer repo.
- `baseBranch` is optional. When omitted, the updater should resolve and target the consumer repository's current default branch.
- V1 only supports `divergencePolicy: "exact"`.
- If a consumer needs durable local customization for a workflow, that file should not be registered as exact-managed until the variation is modeled upstream or split into a different starter template.
- Disabled bindings remain in the manifest for traceability but are skipped.

## 9. Managed file contract

An exact-managed consumer workflow file is treated as a rendered copy of the shared starter template.

That means:
- the updater may replace the whole file content during an update PR
- local edits to that file are treated as divergence
- repo-specific configuration must come through vars, secrets, or approved workflow inputs, not by hand-editing the managed file

## 10. Trigger rules

The shared-repo updater workflow should run on:
- push to `main` when any of these change:
  - `templates/starter-workflows/**`
  - `templates/cross-repo-workflow-distribution-manifest.json`
  - scripts implementing cross-repo distribution
- manual dispatch with optional filters:
  - specific consumer repo
  - specific starter template
  - specific source commit

When a consumer entry omits `baseBranch`, the updater should resolve the repository default branch at runtime, for example from the repository metadata or remote HEAD.

V1 should not trigger cross-repo PR creation from docs-only changes.

## 11. Impact analysis rules

For each updater run:

1. determine which starter templates changed between the previous and current shared-repo commit
2. read the cross-repo distribution manifest
3. find all enabled consumer bindings whose `starterTemplate` is in the changed set
4. group changes by consumer repo
5. produce at most one PR per consumer repo per run

V1 batching rule:
- one updater run may batch multiple managed workflow updates into a single PR for the same consumer repo
- do not mix unrelated repositories in one PR

## 12. Rendering rule

For each impacted binding:
- read the canonical starter template from the shared repo at the current source commit
- write that content to the consumer repo `targetPath`
- preserve only repository-level Git metadata outside the file itself

V1 rendering rule is intentionally simple:
- exact file replacement
- no template variable interpolation inside the shared updater
- no consumer-specific in-file mutation layer

If consumer-specific customization is needed, model it through:
- GitHub vars
- GitHub secrets
- workflow inputs
- or a separate starter template

## 13. Divergence policy

V1 divergence policy is **exact-managed only**.

Meaning:
- if the consumer target file differs from the current starter template, the updater should check whether it still matches a historical revision of that same starter template
- if it matches a historical shared revision, it can still be treated as a safe managed outdated copy
- otherwise, the updater must treat that as divergence
- the updater must not overwrite such a file silently

### V1 divergence handling

When divergence is detected:
- do not overwrite the file automatically
- do not open a normal update PR that hides the conflict
- instead mark the binding as needing manual review
- include the divergence reason in the run summary

Preferred next-step improvement:
- open an **AI-assisted manual-review PR** that does not silently normalize the workflow, but instead presents a bounded divergence report and, when confidence is high enough, may include an explicit proposed normalization patch for human review

That manual-review PR should clearly separate:
- verified diff facts
- interpretation of whether the consumer looks like an older managed copy or an intentional customization
- confidence level and open doubts
- recommendation: normalize now, or adjudicate first

## 14. Provenance tracking

To make exact-managed updates auditable, the updater should record provenance in the PR body.

Required PR metadata:
- shared source repo
- shared source commit SHA
- each starter template path used
- each target consumer workflow path updated
- previous and new pinned reusable-workflow SHA when applicable
- validation status

Optional later enhancement:
- add a lightweight managed comment header to consumer workflow files
- this is not required in V1

## 15. Validation rules

Before opening a consumer PR, the updater must validate:
- every referenced starter template exists in the shared repo at the source commit
- every target path is under `.github/workflows/`
- resulting YAML is syntactically valid
- any expected pinned reusable-workflow `uses: ...@<sha>` refs are present in the rendered file when required by the starter template design

If validation fails:
- do not open the PR
- report the failure clearly in the updater run output

## 16. PR creation behavior

V1 update delivery mode:
- pull request only

Base branch behavior:
- if `baseBranch` is present in a consumer entry, target that branch
- otherwise, target the consumer repo's current default branch resolved at run time

V1 implementation note:
- the first updater implementation lives at `scripts/github/cross_repo_workflow_updater.py`
- it currently relies on local consumer clones for branch resolution and content preview/apply work
- PR creation uses `git` plus an automatic provider chain:
  1. GitHub CLI (`gh`)
  2. GitHub REST API
  3. GitHub GraphQL API
- API-based fallbacks can authenticate from supported environment variables, `gh auth token`, `.netrc`, or embedded HTTPS remote credentials

Recommended follow-up mode:
- when divergence blocks a normal sync PR, the updater may optionally switch to an AI-assisted manual-review PR path that creates a review artifact instead of a silent overwrite
- those review artifacts should normally be treated as temporary adjudication scaffolding, not as permanent repo assets; if normalization is later approved, prefer a clean workflow-change PR rather than merging artifact-only files by accident

Branch naming:
- `chore/sync-shared-workflows-<shortsha>`

PR title format:
- `chore(ci): sync shared workflows from fr-meyer/agent-toolkit@<shortsha>`

PR body must include:
- why the PR exists
- shared source commit
- affected starter templates
- affected consumer target files
- summary of pinned reusable-workflow SHA changes when present
- validation result summary
- note that the PR is safe to revert if needed

V1 merge policy:
- no auto-merge by default
- consumer repo owners review and merge manually

## 17. Rollback behavior

Rollback in this spec means **safe failure handling plus a clean revert path**, not an autonomous recovery engine.

### Before merge

If validation fails:
- do not open a PR

If divergence is detected:
- do not overwrite automatically
- do not open a normal replacement PR
- route the case to manual review

### After merge

If a merged update causes trouble in the consumer repo:
- rollback is performed by reverting the update PR in the consumer repo

V1 rollback rule:
- manual revert is the required baseline capability
- no automatic rollback PR generator is required yet

Possible later enhancement:
- offer an assisted rollback PR that restores the previously managed workflow file version

## 18. Security and auth model

V1 should use credentials that can:
- read this shared repo
- push a branch to the consumer repo or a service-owned fork
- open a PR in the consumer repo

V1 should not require credentials that can:
- force-push consumer default branches
- bypass branch protection
- auto-merge without review unless explicitly enabled later

## 19. Failure policy

A single consumer failure must not abort visibility for all other consumers.

The updater run summary should report per consumer:
- skipped
- updated PR opened
- validation failed
- divergence detected
- auth failure

## 20. Recommended implementation sequence

1. create `templates/cross-repo-workflow-distribution-manifest.json`
2. implement manifest loader and impact analysis script
3. implement exact file rendering for managed consumer bindings
4. implement pre-PR validation
5. implement PR creation for one consumer repo
6. expand to multi-consumer batching with per-consumer summaries
7. add manual-dispatch filters

## 21. Key V1 policy decisions

- canonical distribution unit = starter template
- consumer target update mode = PR only
- file update strategy = exact replacement
- divergence policy = exact-managed only, skip on drift
- rollback policy = revert the PR
- consumer-specific values belong in vars, secrets, and inputs, not hand-edited managed files

## 22. Open follow-up questions after V1

- should we later support stable release tags like `@v1` in addition to pinned SHAs?
- should managed consumer files gain an explicit provenance comment header?
- should divergence produce a diagnostic PR, an issue, or only a run report?
- should update PRs be one-per-consumer-run or one-per-template-binding?
- should there be a consumer self-service install command that also registers the binding automatically?
