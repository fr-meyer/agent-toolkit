# Workflow asset library layout

This repository uses a source-library layout for GitHub Actions assets.

## Goal

Keep workflow files here as canonical source assets, without treating this repository itself as the active GitHub serving surface.

## Canonical layout

```text
agent-toolkit/
├── .github/
│   └── workflows/
│       └── sync-starter-workflow-template-refs.yml
├── templates/
│   ├── reusable-workflows/
│   │   └── coderabbit-pr-automation.yml
│   ├── starter-workflows/
│   │   ├── coderabbit-pr-automation-wrapper.yml
│   │   └── coderabbit-pr-comment-trigger.yml
│   ├── repo-maintenance-workflows/
│   │   └── sync-starter-workflow-template-refs.yml
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

### `templates/starter-workflows/`
Canonical source files for starter workflows that can later be copied or adapted into consumer repositories.

These files may still show the eventual GitHub call shape, such as:

```yaml
uses: owner/repo/.github/workflows/workflow.yml@<ref>
```

That path is a publication target shape, not a statement that the canonical source file in this repository lives under `.github/workflows/` today.

### `scripts/coderabbit/`
Runtime helper scripts used by the CodeRabbit automation flow.

### `templates/repo-maintenance-workflows/`
Canonical source files for repo-local maintenance workflows used by this repository itself.

These are authored under `templates/` on purpose so the repo-local operational workflows follow the same source-library model as the reusable and starter workflow assets.

### `scripts/github/`
Deterministic maintenance or publishing helpers for republishing, pinned-ref maintenance, and materializing repo-local workflow copies from canonical template sources.

### `.github/workflows/`
Materialized live operational copies only.

Files here are runtime copies generated from `templates/repo-maintenance-workflows/` for this repository's own GitHub execution surface.

They are intentionally not the authoring source of truth.

## Why this layout

This avoids mixing up four different concepts:

- **canonical source assets** stored under `templates/`
- **materialized repo-local runtime workflows** under `.github/workflows/`
- **GitHub-special publication paths** like `.github/workflows/` and `.github/workflow-templates/`
- **published targets** that may exist later in another repo, branch, or release flow

The repository stays honest about what it is: a storage and maintenance library for workflow assets, with repo-local runtime files materialized from canonical sources.

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

It does use `.github/workflows/` for repo-local maintenance automation, but those files are materialized runtime copies from canonical sources in `templates/repo-maintenance-workflows/`.

That keeps the authoring model consistent even when this repository needs live GitHub workflow files for its own maintenance.
