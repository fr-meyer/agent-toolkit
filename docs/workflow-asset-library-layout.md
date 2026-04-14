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
│   └── workflow-ref-sync-manifest.json
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

### `scripts/github/`
Optional maintenance or publishing helpers for republishing and pinned-ref maintenance workflows.

This includes the deterministic ref updater used by the repo-local maintenance workflow.

### `.github/workflows/`
Repo-local operational automation only.

Files here may maintain the source library itself, for example by syncing pinned starter-workflow refs after a reusable workflow source asset changes.

These workflow files are not the canonical reusable/starter source assets. Those still live under `templates/`.

## Why this layout

This avoids mixing up four different concepts:

- **source assets** stored in this repository
- **repo-local maintenance automation** used to maintain those assets
- **GitHub-special publication paths** like `.github/workflows/` and `.github/workflow-templates/`
- **published targets** that may exist later in another repo, branch, or release flow

The repository stays honest about what it is: a storage and maintenance library for reusable workflow assets.

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

It may still use `.github/workflows/` for repo-local maintenance automation that acts on the canonical files in `templates/`.

Those can be added back later if there is a real publishing need, but they are intentionally out of the source layout for now.
