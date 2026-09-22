# agent-toolkit

Public shared toolkit for reusable agent skills, GitHub Actions workflow assets, setup scripts, and supporting documentation.

## What this repository contains

- **Shared agent skills** under `skills/`
- **Workflow source assets** under `templates/`
  - reusable workflow sources under `templates/reusable-workflows/`
  - starter workflow sources under `templates/starter-workflows/`
- **Setup and linking scripts** under `scripts/`
- **Publication-safety helpers** such as `scripts/public-pr-safety-scan`
- **Repository-work deduplication** via `skills/repository-similarity-preflight`
- **Shared Cursor assets** under `cursor/`
- **Reference and setup docs** under `docs/`

## Current skill set

### Research-paper workflows
- `classify-research-papers`
- `pageindex-find-papers`
- `pageindex-read-papers`
- `pageindex-summarize-papers`
- `summarize-research-papers`

### Legacy reviewer compatibility
- CodeRabbit workflow automation has been retired from this toolkit.
- Historical CodeRabbit skill directories remain isolated for compatibility and are not wired into active workflows.

### Repo maintenance and publication safety
- `git-repo-sync`
- `changeset-commit-partitioner`
- `public-repo-red-list-audit`
- `public-repo-red-list-remediation`
- `github-pr-preflight`
- `repository-similarity-preflight`
- `repo-documentation-audit`
- `repo-documentation-drift-fix`

### Toolkit integration and skill authoring
- `connect-openclaw-toolkit`
- `portable-skill-authoring`

## Repository layout

```text
agent-toolkit/
├── .github/
│   └── workflows/
│       ├── sync-starter-workflow-template-refs-reusable.yml
│       ├── sync-starter-workflow-template-refs-trigger.yml
│       ├── cross-repo-workflow-updater-reusable.yml
│       ├── cross-repo-workflow-updater-push-trigger.yml
│       └── cross-repo-workflow-updater-manual-trigger.yml
├── templates/
│   ├── reusable-workflows/
│   │   ├── sync-starter-workflow-template-refs-reusable.yml
│   │   └── cross-repo-workflow-updater-reusable.yml
│   ├── starter-workflows/
│   │   ├── sync-starter-workflow-template-refs-trigger.yml
│   │   ├── cross-repo-workflow-updater-push-trigger.yml
│   │   └── cross-repo-workflow-updater-manual-trigger.yml
│   ├── workflow-ref-sync-manifest.json
│   └── repo-workflow-materialization-manifest.json
├── skills/
├── scripts/
├── docs/
├── cursor/
├── LICENSE
└── README.md
```

## Quick start

By default, local tooling resolves this repository through `~/.agent-toolkit`.

```bash
ln -s /path/to/your/clone ~/.agent-toolkit
```

Then use the setup helpers:

```bash
~/.agent-toolkit/scripts/connect-openclaw.sh
~/.agent-toolkit/scripts/connect-cursor.sh
~/.agent-toolkit/scripts/verify-links.sh
```

If you do not want to use the default alias, the scripts also support explicit path overrides. See `docs/setup.md` for the full flag and environment-variable matrix.

## Public PR safety scan

Use `scripts/public-pr-safety-scan` as a deterministic backstop after creating or editing a public or public-intended GitHub pull request:

```bash
scripts/public-pr-safety-scan owner/repo 123 --denylist-file .public-pr-safety-denylist.local
```

The committed scanner contains only generic structural checks. Put project-specific names, local labels, and case-specific terms in `.public-pr-safety-denylist.local`, which is ignored by git. The command scans the PR title, body, and hosted `.patch`/`.diff` views, redacting matched text in normal output.

## GitHub Actions workflow assets

This repository stores only the remaining maintenance and distribution workflow
assets. CodeRabbit remediation workflows, starter templates, helper scripts, and
consumer bindings were retired because Mergeguez is now the first-party review
lane and Speculoos owns review evidence and merge planning.

- **Reusable maintenance workflow source:** `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- **Starter workflow sources:** `templates/starter-workflows/`
- **Ref-sync manifest:** `templates/workflow-ref-sync-manifest.json`
- **Repo-workflow materialization manifest:** `templates/repo-workflow-materialization-manifest.json`
- **Cross-repo distribution manifest:** `templates/cross-repo-workflow-distribution-manifest.json`
- **Helper scripts:** `scripts/github/`
- **Architecture note:** `docs/workflow-asset-library-layout.md`
- **Workflow catalog:** `docs/github-actions-template-catalog.md`

The remaining workflow assets are deterministic maintenance plumbing only. They do
not review pull requests, invoke Mergeguez, fix findings, commit remediation
changes, or grant merge authority.

## Shared-content boundary

This repository is for **shared, reusable content only**. It should not contain machine-local auth state, secrets, personal environment dumps, clone-specific configuration, or packaged release bundles tracked in source control. For the full scope boundary, see `docs/repo-scope.md`.

## Documentation map

- `docs/setup.md` — setup, linking, overrides, verification, and repo-rename migration
- `docs/repo-scope.md` — what belongs in the repo and what does not
- `docs/workflow-asset-library-layout.md` — canonical layout for workflow source assets in this repository
- `docs/github-actions-template-catalog.md` — human-readable catalog of available workflow assets, their purpose, and how they relate
- `docs/workflow-authoring-rules.md` — workflow classification and edit rules for humans and agents
- `scripts/public-pr-safety-scan` — deterministic public PR title/body and hosted patch/diff safety scanner
- `AGENTS.md` — repo-local operating instructions and doc map for future agents
- `cursor/rules/README.md` — how shared Cursor rules are linked into projects

## License

MIT, see `LICENSE`.
