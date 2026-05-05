# agent-toolkit

Public shared toolkit for reusable agent skills, GitHub Actions workflow assets, Cursor assets, and supporting documentation.

## What this repository contains

- **Shared agent skills** under `skills/`
- **Workflow source assets** under `templates/`
  - reusable workflow sources under `templates/reusable-workflows/`
  - starter workflow sources under `templates/starter-workflows/`
- **Workflow helper scripts** under `scripts/`
- **Shared Cursor assets** under `cursor/`
- **Reference and setup docs** under `docs/`

## Current skill set

### Research-paper workflows
- `classify-research-papers`
- `pageindex-find-papers`
- `pageindex-read-papers`
- `pageindex-summarize-papers`
- `summarize-research-papers`
- `zotero-docai-ingest-to-pageindex`
- `zotero-tagged-literature-review`

### Code review and GitHub automation
- `coderabbit-pr-autofix`
- `coderabbit-pr-automation`
- `github-workflow-asset-library`

> Official CodeRabbit skills such as `autofix` and `code-review` are intentionally sourced from the upstream `coderabbitai/skills` repository, not duplicated here.

### Repo maintenance and publication safety
- `git-repo-sync`
- `changeset-commit-partitioner`
- `public-repo-red-list-audit`
- `public-repo-red-list-remediation`
- `repo-documentation-audit`
- `repo-documentation-drift-fix`

### Skill authoring
- `skill-creator`

## Repository layout

```text
agent-toolkit/
├── .github/
│   └── workflows/
├── templates/
│   ├── reusable-workflows/
│   ├── starter-workflows/
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

Clone this repo wherever you keep GitHub repositories, then point OpenClaw at the `skills/` directory with `skills.load.extraDirs`.

Example with this toolkit plus upstream CodeRabbit skills:

```bash
openclaw config set skills.load.extraDirs '["/path/to/agent-toolkit/skills","/path/to/coderabbitai-skills/skills"]' --strict-json
openclaw config validate
```

Do **not** symlink this repository into `~/.openclaw/skills` or `~/.openclaw/scripts`. OpenClaw skill loading should be explicit through config, and runtime scripts required by a skill should live inside that skill's own `scripts/` directory. Repo-level scripts are reserved for repository, CI, distribution, and integration automation.

For shared Cursor rules, see `docs/setup.md`.

## GitHub Actions workflow assets

This repository treats GitHub Actions files as **source assets**, not as active GitHub-special paths for this repo.

- **Reusable workflow source:** `templates/reusable-workflows/coderabbit-pr-automation.yml`
- **Reusable maintenance workflow source:** `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`
- **Starter workflow sources:** `templates/starter-workflows/`, including `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- **CodeRabbit split-trigger starter sources:** `templates/starter-workflows/coderabbit-pr-automation-pr-trigger.yml` and `templates/starter-workflows/coderabbit-pr-automation-manual-trigger.yml`
- **Ref-sync manifest:** `templates/workflow-ref-sync-manifest.json`
- **Repo-workflow materialization manifest:** `templates/repo-workflow-materialization-manifest.json`
- **Helper scripts:** `scripts/coderabbit/` plus `scripts/github/` (including the deterministic ref updater and repo-workflow materializer)
- **Materialized live reusable maintenance workflow:** `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`
- **Live repo entrypoint workflow:** `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`
- **Architecture note:** `docs/workflow-asset-library-layout.md`
- **Workflow catalog:** `docs/github-actions-template-catalog.md`

The intended split is:
- this repository stores the canonical workflow source assets under `templates/`
- reusable workflow sources are meant to be published later into `.github/workflows/` of a serving repository
- starter workflow sources are meant to be copied or adapted into consumer repositories later
- every live workflow under `.github/workflows/` should have a canonical source under `templates/`
- workflow classification is based on role, not on whether this repo happens to execute a rendered copy locally
- repo-local GitHub execution can use thin entrypoint workflows under `.github/workflows/` that call materialized reusable workflow copies
- `.github/workflows/` contains the live runtime files used by this repository at runtime, while reusable workflow source of truth stays under `templates/reusable-workflows/`

Current workflow-maintenance policy:
- workflow-maintenance branches are created from `dev`
- repo-local workflow-sync automation opens a dedicated PR instead of pushing maintenance commits directly onto the triggering branch
- cross-repo workflow divergence is reviewed through managed PR comments by default, not committed `docs/shared-workflow-reviews/*` files

Important note for the current starter workflow sources:
- they still show the eventual GitHub reusable-workflow serving path shape, for example `owner/repo/.github/workflows/<file>@<ref>`
- that `uses:` path is a publication-target shape, not a claim that this source-library repo currently serves that workflow at HEAD
- if you publish these assets later, keep the `uses: ...@<sha>` reference aligned with the paired `shared_repository_ref` when that field is present

Current runtime contract for the CodeRabbit workflow source:
- choose the coding-agent runtime with `CODERABBIT_AGENT_RUNTIME` (for example `cursor`)
- keep the actual remediation command explicit via `CODERABBIT_AGENT_COMMAND_JSON` or `CODERABBIT_AGENT_COMMAND`
- provide `CURSOR_API_KEY` when using `cursor`
- for the current free-tier path, default to `run_validation: false`
- shared Agent Skills can be installed into the target repo via `install_shared_skills`
- shared Cursor rules can be installed into the target repo via `install_cursor_rules`
- the default install mode for shared agent context is `copy`
- optional local post-remediation commit creation can be enabled via `auto_commit`
- split-by-scope autocommit can run in `auto` or `fixed` commit-count mode
- commit planning and commit-message drafting are delegated to the installed Git skills rather than hardcoded into the workflow
- provide `CODERABBIT_API_KEY` only when CodeRabbit CLI validation is explicitly enabled

## Shared-content boundary

This repository is for **shared, reusable content only**. It should not contain machine-local auth state, secrets, personal environment dumps, clone-specific configuration, or packaged release bundles tracked in source control. For the full scope boundary, see `docs/repo-scope.md`.

## Documentation map

- `docs/setup.md` — OpenClaw `extraDirs` setup, Cursor rules setup, path overrides, and repo-rename notes
- `docs/repo-scope.md` — what belongs in the repo and what does not
- `docs/workflow-asset-library-layout.md` — canonical layout for workflow source assets in this repository
- `docs/github-actions-template-catalog.md` — human-readable catalog of available workflow assets, their purpose, and how they relate
- `docs/workflow-authoring-rules.md` — workflow classification and edit rules for humans and agents
- `AGENTS.md` — repo-local operating instructions and doc map for future agents
- `scripts/coderabbit/README.md` — runtime notes for the CodeRabbit helper scripts
- `cursor/rules/README.md` — how shared Cursor rules are linked into projects

## License

MIT, see `LICENSE`.
