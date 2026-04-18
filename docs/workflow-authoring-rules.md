# Workflow authoring rules

This document defines the durable workflow-layout rule for this repository.

## Core rule

Every workflow that exists under `.github/workflows/` should have a canonical source under `templates/`.

Live files under `.github/workflows/` are runtime copies, not the preferred authoring location.

## Token and configuration naming rule

Prefer GitHub's built-in `GITHUB_TOKEN` for default GitHub authentication.

Do not introduce ad hoc alias names just to forward the built-in token through starter workflows or reusable workflows.

Use `ELEVATED_GITHUB_TOKEN` as the single explicit override when the built-in token is not enough, for example:
- cross-repo clone, branch, PR, or write operations
- privileged writes, including pushes that touch `.github/workflows/**`
- private shared-repository access that the built-in token cannot read

When a workflow can run with default auth but may occasionally need stronger auth, code it to fall back from `ELEVATED_GITHUB_TOKEN` to `secrets.GITHUB_TOKEN`.

Keep third-party secrets product-scoped, for example `CURSOR_API_KEY` and `CODERABBIT_API_KEY`, and keep workflow variables namespaced by workflow family, for example `CODERABBIT_*`.

Important GitHub nuance:
- the built-in `GITHUB_TOKEN` is provided by Actions
- do not assume you can override it by creating a manual repository secret with the same name
- if stronger auth is required, add a separate explicit secret such as `ELEVATED_GITHUB_TOKEN`

## Classification rule

Classify workflow templates by **role**, not by where a rendered copy happens to run.

### `templates/reusable-workflows/`

Use this folder for callable reusable workflows, typically workflows with `on: workflow_call`.

These are source assets that may later be published into `.github/workflows/` of a serving repository.

### `templates/starter-workflows/`

Use this folder for copy/adapt entrypoints and consumer-facing workflow templates.

This includes repo-local trigger entrypoints when their canonical form should remain reusable as a template, even if this repository materializes a live copy under `.github/workflows/` for its own runtime.

When different trigger surfaces exist primarily for clarity rather than shared logic, prefer separate starter workflows over a single multi-trigger wrapper with trigger-gated sibling jobs. This keeps consumer CI signals cleaner and avoids irrelevant skipped jobs.

## Current maintenance-flow example

- Canonical reusable engine:
  - `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- Canonical trigger/entrypoint template:
  - `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- Materialized runtime copies:
  - `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
  - `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`

## Current automation policy

- Dedicated automation branches must start from `dev`.
- Repo-local workflow maintenance changes should be proposed in a separate PR, not pushed directly back onto the triggering branch.
- Cross-repo divergence review should be attached to the update PR as a managed PR comment by default.

## Manifest responsibilities

### `templates/repo-workflow-materialization-manifest.json`

This manifest controls **template source -> live `.github/workflows/` copy** materialization.

Use it when:
- a canonical template should render to a live `.github/workflows/` file
- a live workflow target is renamed
- a materialized workflow is added or removed

### `templates/workflow-ref-sync-manifest.json`

This manifest controls **reusable workflow source -> target file SHA diffusion**.

Each managed mapping answers:
- which reusable workflow source is authoritative
- which published `.github/workflows/...` path that reusable workflow represents
- which target files should have their pinned `uses: ...@<sha>` refs updated when the reusable source changes

Those targets may include:
- starter templates under `templates/starter-workflows/`
- linked live workflows under `.github/workflows/`

Update this manifest whenever:
- a reusable workflow should diffuse its pinned SHA into new targets
- a target file is added, removed, or renamed
- a reusable workflow source path or published workflow path changes

## When creating or modifying a workflow

1. Decide the workflow role first.
   - `workflow_call` reusable asset -> `templates/reusable-workflows/`
   - copy/adapt entrypoint or starter -> `templates/starter-workflows/`
2. Edit the canonical template source under `templates/`.
3. Update `templates/repo-workflow-materialization-manifest.json` if a live `.github/workflows/` copy must be materialized.
4. Decide whether the reusable workflow needs SHA diffusion into starter templates, linked live workflows, or both.
5. Update `templates/workflow-ref-sync-manifest.json` whenever that source-to-target binding changes.
6. Re-materialize the live `.github/workflows/` copies.
7. Validate that pinned `uses: ...@<sha>` refs were updated correctly, and validate `shared_repository_ref` too when that field exists.
8. Update the relevant docs if the architecture or rules changed.

## Current diffusion rule

The ref-sync system updates the matching pinned `uses: ...@<sha>` ref in each mapped target.

When a paired `shared_repository_ref` field exists, it should be updated to the same SHA. Some targets may not have that field, and that is allowed.

## Why this rule exists

- keeps the repo honest as a workflow asset library
- avoids silent drift between template source and live runtime copies
- preserves future reuse in other repos
- gives both humans and agents one predictable authoring model
