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

### Retired reviewer assets
- CodeRabbit workflows, templates, helper scripts, and skills have been retired from this toolkit.

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
│       ├── cross-repo-workflow-updater-manual-trigger.yml
│       ├── pr-automation-dogfood-reusable.yml
│       ├── pr-automation-dogfood-pr-trigger.yml
│       └── repository-similarity-preflight-ci.yml
├── templates/
│   ├── reusable-workflows/
│   │   ├── sync-starter-workflow-template-refs-reusable.yml
│   │   ├── cross-repo-workflow-updater-reusable.yml
│   │   └── pr-automation-dogfood-reusable.yml
│   ├── starter-workflows/
│   │   ├── sync-starter-workflow-template-refs-trigger.yml
│   │   ├── cross-repo-workflow-updater-push-trigger.yml
│   │   ├── cross-repo-workflow-updater-manual-trigger.yml
│   │   ├── pr-automation-dogfood-pr-trigger.yml
│   │   └── repository-similarity-preflight-ci.yml
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

This repository stores the retained maintenance, distribution, Pullfrog, and
Speculoos workflow assets. CodeRabbit remediation workflows, starter templates,
helper scripts, and consumer bindings were retired. Pullfrog remains the required
exact-head AI review lane, Speculoos validates exact-head evidence, and Mergeguez
remains the guarded publication and merge broker.

- **Reusable maintenance workflow source:** `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- **Starter workflow sources:** `templates/starter-workflows/`, including `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- **Repository similarity preflight CI source:** `templates/starter-workflows/repository-similarity-preflight-ci.yml`
- **Ref-sync manifest:** `templates/workflow-ref-sync-manifest.json`
- **Repo-workflow materialization manifest:** `templates/repo-workflow-materialization-manifest.json`
- **Cross-repo distribution manifest:** `templates/cross-repo-workflow-distribution-manifest.json`
- **Provider-free PR automation dogfood:** `docs/pr-automation-dogfood.md`
- **Bounded Pullfrog review-only pilot:** `docs/pullfrog-review-only-pilot.md`, with canonical workflow source at `templates/starter-workflows/pullfrog.yml`
- **Activation-gated Pullfrog review fallback:** `docs/pullfrog-review-model-fallback.md`, with canonical workflow source at `templates/starter-workflows/pullfrog-review-fallback.yml` and composite exact-head check `pullfrog-review-gate`
- **Independent Speculoos PR gate:** `templates/starter-workflows/speculoos.yml`, materialized to `.github/workflows/speculoos.yml`, with zero-secret hosted contract validation in `scripts/github/speculoos_pr_contract.py`
- **Materialized live reusable maintenance workflow:** `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
- **Live repo entrypoint workflow:** `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`
- **Architecture note:** `docs/workflow-asset-library-layout.md`
- **Workflow catalog:** `docs/github-actions-template-catalog.md`

The retained ref-sync and distribution workflows are deterministic maintenance
plumbing only; those maintenance workflows neither invoke Mergeguez nor grant
merge authority. Pullfrog review and separately gated remediation assets remain
independent, while Speculoos validates their exact-head contract. The retained
cloud remediation loop has a separate policy-gated exact-head non-stable
auto-merge controller; Pullfrog-native and stable-branch auto-merge remain
disabled.

## Shared-content boundary

This repository is for **shared, reusable content only**. It should not contain machine-local auth state, secrets, personal environment dumps, clone-specific configuration, or packaged release bundles tracked in source control. For the full scope boundary, see `docs/repo-scope.md`.

## Documentation map

- `docs/setup.md` — setup, linking, overrides, verification, and repo-rename migration
- `docs/repo-scope.md` — what belongs in the repo and what does not
- `docs/workflow-asset-library-layout.md` — canonical layout for workflow source assets in this repository
- `docs/github-actions-template-catalog.md` — human-readable catalog of available workflow assets, their purpose, and how they relate
- `docs/workflow-authoring-rules.md` — workflow classification and edit rules for humans and agents
- `docs/pullfrog-review-only-pilot.md` — immutable action custody and non-merging pilot boundary
- `scripts/public-pr-safety-scan` — deterministic public PR title/body and hosted patch/diff safety scanner
- `AGENTS.md` — repo-local operating instructions and doc map for future agents
- `cursor/rules/README.md` — how shared Cursor rules are linked into projects

## License

MIT, see `LICENSE`.
