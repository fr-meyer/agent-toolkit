# Workflow asset library layout

This repository uses a source-library layout for GitHub Actions assets.

## Goal

Keep workflow files here as canonical source assets, without treating this repository itself as the active GitHub serving surface.

## Canonical layout

```text
agent-toolkit/
├── .github/
│   └── workflows/
│       ├── sync-starter-workflow-template-refs-reusable.yml
│       └── sync-starter-workflow-template-refs-trigger.yml
├── templates/
│   ├── reusable-workflows/
│   │   ├── coderabbit-pr-automation.yml
│   │   └── sync-starter-workflow-template-refs-reusable.yml
│   ├── starter-workflows/
│   │   ├── coderabbit-pr-automation-wrapper.yml
│   │   ├── coderabbit-pr-comment-trigger.yml
│   │   └── sync-starter-workflow-template-refs-trigger.yml
│   ├── workflow-ref-sync-manifest.json
│   └── repo-workflow-materialization-manifest.json
├── scripts/
│   ├── coderabbit/
│   └── github/
└── docs/
```

## Folder responsibilities

### `templates/reusable-workflows/`
Canonical source files for reusable workflows.

These are not stored under `.github/workflows/` here because this repository is acting as a library of source assets, not as the live serving repo for GitHub reusable workflows.

That includes reusable maintenance workflows that this repository later materializes into repo-local callable files under `.github/workflows/`.

### `templates/starter-workflows/`
Canonical source files for starter workflows that can later be copied or adapted into consumer repositories.

These files may still show the eventual GitHub call shape, such as:

```yaml
uses: owner/repo/.github/workflows/workflow.yml@<ref>
```

That path is a publication target shape, not a statement that the canonical source file in this repository lives under `.github/workflows/` today.

Repo-local trigger entrypoints that are intended to be copied or adapted later should also live here as canonical starter sources, even if this repository materializes a live copy under `.github/workflows/` for its own runtime.

### `scripts/coderabbit/`
Runtime helper scripts used by the CodeRabbit automation flow.


### `scripts/github/`
Deterministic maintenance or publishing helpers for republishing, pinned-ref maintenance, and materializing repo-local workflow copies from canonical template sources.

### `.github/workflows/`
Live repo execution files only.

Materialized reusable workflow copies can live here so GitHub can call them.

Thin repo-local entrypoint workflows can also live here when this repository needs a trigger surface that calls a reusable workflow implementation.

The reusable workflow source of truth still lives under `templates/reusable-workflows/`.

The source of truth for repo-local trigger entrypoints lives under `templates/starter-workflows/`.

## Why this layout

This avoids mixing up four different concepts:

- **canonical source assets** stored under `templates/`
- **materialized repo-local callable reusable workflows** under `.github/workflows/`
- **repo-local trigger entrypoints** under `.github/workflows/`
- **GitHub-special publication paths** like `.github/workflows/` and `.github/workflow-templates/`
- **published targets** that may exist later in another repo, branch, or release flow

Classification is based on **role**, not on whether a rendered copy happens to run in this repository:

- callable `workflow_call` assets belong in `templates/reusable-workflows/`
- copy/adapt entrypoints belong in `templates/starter-workflows/`
- every live `.github/workflows/` file should be a rendered/materialized copy of a canonical template source

The repository stays honest about what it is: a storage and maintenance library for workflow assets, with repo-local execution files only where GitHub requires them.

## Publication model

If these assets are later published for real GitHub consumption:

- reusable workflow sources from `templates/reusable-workflows/` should be copied into `.github/workflows/` of the chosen serving repo
- starter workflow sources from `templates/starter-workflows/` should be copied into consumer repos, or transformed for another publishing surface if needed

## Pinning rule

When a starter workflow calls a reusable workflow, keep these aligned:

- `uses: owner/repo/.github/workflows/file.yml@<sha>`
- `shared_repository_ref: <same sha>`

If they diverge, the starter workflow no longer describes a coherent published target.

## Current scope

This repository is **not** currently using:

- `.github/workflows/` as its canonical storage layout for workflow source assets
- `.github/workflow-templates/` as its canonical storage layout
- GitHub native template-picker metadata as part of the active architecture

For the current maintenance flow, the canonical reusable implementation lives in `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`, gets materialized to `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`, and is called by the live trigger entrypoint `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`, whose canonical source lives in `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`.
