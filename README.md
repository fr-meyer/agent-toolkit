# agent-toolkit

Public shared toolkit for reusable agent skills, GitHub Actions workflow assets, setup scripts, and supporting documentation.

## What this repository contains

- **Shared agent skills** under `skills/`
- **Reusable GitHub Actions assets** under `.github/`
  - a reusable workflow: `.github/workflows/coderabbit-pr-automation.yml`
  - a thin workflow template draft: `.github/workflow-templates/coderabbit-pr-automation-wrapper.yml`
- **Setup and linking scripts** under `scripts/`
- **Shared Cursor assets** under `cursor/`
- **Reference and setup docs** under `docs/`

## Current skill set

### Research-paper workflows
- `classify-research-papers`
- `pageindex-find-papers`
- `pageindex-read-papers`
- `pageindex-summarize-papers`
- `summarize-research-papers`

### Code review and GitHub automation
- `autofix`
- `code-review`
- `coderabbit-pr-autofix`
- `coderabbit-pr-automation`

### Repo maintenance and publication safety
- `git-repo-sync`
- `changeset-commit-partitioner`
- `public-repo-red-list-audit`
- `public-repo-red-list-remediation`
- `repo-documentation-audit`
- `repo-documentation-drift-fix`

### Toolkit integration and skill authoring
- `connect-openclaw-toolkit`
- `skill-creator`

## Repository layout

```text
agent-toolkit/
├── .github/
│   ├── workflows/
│   │   └── coderabbit-pr-automation.yml
│   └── workflow-templates/
│       ├── coderabbit-pr-automation-wrapper.yml
│       └── coderabbit-pr-automation-wrapper.properties.json
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

## GitHub Actions assets

This repository includes a reusable CodeRabbit remediation workflow plus the supporting helper scripts that back it.

- **Reusable workflow:** `.github/workflows/coderabbit-pr-automation.yml`
- **Helper scripts:** `scripts/coderabbit/`
- **Template draft:** `.github/workflow-templates/coderabbit-pr-automation-wrapper.yml`
- **Publishing guidance for an org-level `.github` repo:** `docs/org-github-repo-workflow-template-layout.md`

The intended split is:
- this repository owns the reusable implementation and helper scripts
- an organization-level public `.github` repository owns the workflow-template publishing surface
- the reusable workflow can install shared Agent Skills into `.agents/skills` inside the checked-out consumer repo on the runner
- the reusable workflow can install shared Cursor rules into `.cursor/rules` inside the checked-out consumer repo on the runner
- consumer repositories keep only thin wrapper workflows, repo-specific variables, and secrets

Current runtime contract for the CodeRabbit workflow:
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

- `docs/setup.md` — setup, linking, overrides, verification, and repo-rename migration
- `docs/repo-scope.md` — what belongs in the repo and what does not
- `docs/org-github-repo-workflow-template-layout.md` — how to publish the workflow template through an org `.github` repo
- `docs/org-github-repo-README.example.md` — example README for that org `.github` repository
- `scripts/coderabbit/README.md` — runtime notes for the CodeRabbit helper scripts
- `cursor/rules/README.md` — how shared Cursor rules are linked into projects

## License

MIT, see `LICENSE`.
