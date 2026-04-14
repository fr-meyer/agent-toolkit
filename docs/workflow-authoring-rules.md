# Workflow authoring rules

This document defines the durable workflow-layout rule for this repository.

## Core rule

Every workflow that exists under `.github/workflows/` should have a canonical source under `templates/`.

Live files under `.github/workflows/` are runtime copies, not the preferred authoring location.

## Classification rule

Classify workflow templates by **role**, not by where a rendered copy happens to run.

### `templates/reusable-workflows/`

Use this folder for callable reusable workflows, typically workflows with `on: workflow_call`.

These are source assets that may later be published into `.github/workflows/` of a serving repository.

### `templates/starter-workflows/`

Use this folder for copy/adapt entrypoints and consumer-facing workflow templates.

This includes repo-local trigger entrypoints when their canonical form should remain reusable as a template, even if this repository materializes a live copy under `.github/workflows/` for its own runtime.

## Current maintenance-flow example

- Canonical reusable engine:
  - `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- Canonical trigger/entrypoint template:
  - `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- Materialized runtime copies:
  - `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
  - `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`

## When creating or modifying a workflow

1. Decide the workflow role first.
   - `workflow_call` reusable asset -> `templates/reusable-workflows/`
   - copy/adapt entrypoint or starter -> `templates/starter-workflows/`
2. Edit the canonical template source under `templates/`.
3. Update `templates/repo-workflow-materialization-manifest.json` if a live `.github/workflows/` copy must be materialized.
4. Update `templates/workflow-ref-sync-manifest.json` if starter templates need pinned reusable-workflow refs kept in sync.
5. Re-materialize the live `.github/workflows/` copies.
6. Update the relevant docs if the architecture or rules changed.

## Why this rule exists

- keeps the repo honest as a workflow asset library
- avoids silent drift between template source and live runtime copies
- preserves future reuse in other repos
- gives both humans and agents one predictable authoring model
