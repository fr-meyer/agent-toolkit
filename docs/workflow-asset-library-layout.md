# Workflow asset library layout

This repository uses a source-library layout for GitHub Actions assets.

For the inventory of currently available workflow assets and their purpose, see `docs/github-actions-template-catalog.md`.

## Goal

Keep workflow files here as canonical source assets, without treating this repository itself as the active GitHub serving surface.

## Canonical layout

```text
agent-toolkit/
├── .github/
│   └── workflows/
│       ├── coderabbit-pr-automation.yml
│       ├── coderabbit-pr-comment-trigger.yml
│       ├── sync-starter-workflow-template-refs-reusable.yml
│       ├── cross-repo-workflow-updater-reusable.yml
│       ├── cross-repo-workflow-updater-push-trigger.yml
│       ├── cross-repo-workflow-updater-manual-trigger.yml
│       ├── pr-automation-dogfood-reusable.yml
│       ├── pr-automation-dogfood-pr-trigger.yml
│       ├── pullfrog.yml
│       ├── pullfrog-cloud-coordinator-dry-run.yml
│       ├── pullfrog-review-fallback.yml
│       ├── pullfrog-cloud-remediation-loop.yml
│       ├── speculoos.yml
│       └── repository-similarity-preflight-ci.yml
├── templates/
│   ├── reusable-workflows/
│   │   ├── coderabbit-pr-automation.yml
│   │   ├── sync-starter-workflow-template-refs-reusable.yml
│   │   ├── cross-repo-workflow-updater-reusable.yml
│   │   └── pr-automation-dogfood-reusable.yml
│   ├── starter-workflows/
│   │   ├── coderabbit-pr-automation-pr-trigger.yml
│   │   ├── coderabbit-pr-automation-manual-trigger.yml
│   │   ├── coderabbit-pr-comment-trigger.yml
│   │   ├── sync-starter-workflow-template-refs-trigger.yml
│   │   ├── cross-repo-workflow-updater-push-trigger.yml
│   │   ├── cross-repo-workflow-updater-manual-trigger.yml
│   │   ├── pr-automation-dogfood-pr-trigger.yml
│   │   ├── pullfrog.yml
│   │   ├── pullfrog-cloud-coordinator-dry-run.yml
│   │   ├── pullfrog-review-fallback.yml
│   │   ├── pullfrog-cloud-remediation-loop.yml
│   │   ├── speculoos.yml
│   │   └── repository-similarity-preflight-ci.yml
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

## Manifest binding rule

Two manifests govern the durable source-to-target behavior:

- `templates/repo-workflow-materialization-manifest.json`
  - binds canonical template sources under `templates/` to live runtime copies under `.github/workflows/`
- `templates/workflow-ref-sync-manifest.json`
  - binds reusable workflow sources to the target files whose pinned reusable-workflow refs should be diffused automatically

The second manifest can target:
- starter templates under `templates/starter-workflows/`
- linked live workflows under `.github/workflows/`

When adding or renaming a reusable workflow, decide explicitly whether it needs:
- no ref diffusion
- diffusion into starter templates only
- diffusion into starter templates plus linked live workflows

Then update the manifest accordingly.

## Pinning rule

When a target workflow calls a reusable workflow, keep the pinned `uses: owner/repo/.github/workflows/file.yml@<sha>` ref aligned with the authoritative reusable workflow commit.

When the target also carries `shared_repository_ref`, keep that field aligned to the same SHA.

If they diverge, the target no longer describes a coherent published target.

## Current scope

This repository is **not** currently using:

- `.github/workflows/` as its canonical storage layout for workflow source assets
- `.github/workflow-templates/` as its canonical storage layout
- GitHub native template-picker metadata as part of the active architecture

For the current maintenance flow, the canonical reusable implementation lives in `templates/reusable-workflows/sync-starter-workflow-template-refs-reusable.yml`, gets materialized to `.github/workflows/sync-starter-workflow-template-refs-reusable.yml`, and is called by the live trigger entrypoint `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`, whose canonical source lives in `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`.

The cross-repo updater follows the same layout pattern: its canonical reusable engine lives in `templates/reusable-workflows/cross-repo-workflow-updater-reusable.yml`, its canonical push trigger wrapper lives in `templates/starter-workflows/cross-repo-workflow-updater-push-trigger.yml`, its canonical manual trigger wrapper lives in `templates/starter-workflows/cross-repo-workflow-updater-manual-trigger.yml`, and all three materialize to matching live copies under `.github/workflows/`.

The repository-similarity preflight CI is a standalone repo-local entrypoint. Its canonical source lives in `templates/starter-workflows/repository-similarity-preflight-ci.yml` and materializes to `.github/workflows/repository-similarity-preflight-ci.yml`; it does not participate in reusable-workflow ref diffusion.

The PR automation dogfood pair also follows this pattern. Its canonical reusable harness lives in `templates/reusable-workflows/pr-automation-dogfood-reusable.yml`, its canonical pull-request trigger lives in `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml`, and both materialize to matching live copies under `.github/workflows/`. The trigger uses a relative same-commit call, so this pair does not need reusable-workflow SHA diffusion.

The bounded Pullfrog entrypoint follows the standalone-starter pattern. Its canonical source lives in `templates/starter-workflows/pullfrog.yml` and materializes to `.github/workflows/pullfrog.yml`. It pins the Pullfrog action and checkout action to immutable commits, explicitly selects `openai/gpt-sol` at `xhigh`, disables pushes, keeps the shell restricted, and maps no provider secret. Pullfrog is the sole intended AI reviewer and future fixer, but write-capable activation remains separately gated. See `docs/pullfrog-review-only-pilot.md` for the historical pilot and `docs/pullfrog-cloud-coordinator.md` for the current architecture.

The activation-gated Pullfrog review fallback is a separate standalone starter. Its canonical source lives in `templates/starter-workflows/pullfrog-review-fallback.yml` and materializes to `.github/workflows/pullfrog-review-fallback.yml`. It permits one `openai/gpt-astra` at `xhigh` review only after the exact recorded Sol cybersecurity-policy refusal on an unchanged same-repository PR head/base, separates provider and check-write authority, and emits the composite exact-head `pullfrog-review-gate`. Source availability does not enable the variable, authorize a hosted pilot, integrate gate consumers, or change required checks. See `docs/pullfrog-review-model-fallback.md`.

The Pullfrog cloud coordinator dry run is another standalone starter. Its canonical source lives in `templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml` and materializes to `.github/workflows/pullfrog-cloud-coordinator-dry-run.yml`. It uses only read permissions and immutable action pins, collects bounded GitHub evidence, evaluates the exact-head contract and destination guard, and uploads a sanitized receipt. It never invokes a provider or performs a repository mutation.

The separately gated Pullfrog cloud remediation loop follows the same standalone-starter pattern. Its canonical source lives in `templates/starter-workflows/pullfrog-cloud-remediation-loop.yml` and materializes to `.github/workflows/pullfrog-cloud-remediation-loop.yml`. It isolates native Pullfrog `fix_review` execution from a fresh read-only validator and from the trusted publisher, persists identity-bound claims and terminal history, and permits only one normal exact-head fast-forward push after a canonical sealed patch and post-patch guards pass. The publisher alone uses the separately provisioned `PULLFROG_REMEDIATION_PUBLISH_TOKEN` so the push emits the normal synchronize event and schedules fresh Pullfrog, CI, and Speculoos evidence. The source is not hosted activation authority; credential provisioning, publication, and the first write pilot remain separately approval-gated.

The independent Speculoos PR gate follows the standalone-starter pattern. Its canonical source lives in `templates/starter-workflows/speculoos.yml` and materializes to `.github/workflows/speculoos.yml`. It runs read-only on the exact PR head, binds the manifest's current task to the live head and base, and executes the repository-bound zero-secret contract validator at `scripts/github/speculoos_pr_contract.py`. Candidate-facing Python entrypoints use isolated mode, and the workflow validator executes each allowlisted policy test directly rather than prepending a candidate-controlled discovery directory, so a repository file such as `scripts/github/argparse.py`, `scripts/github/tests/json.py`, or a root-level standard-library namesake cannot replace the interpreter's trusted imports. The validator checks the complete diff packet, including deleted paths, canonical release wording, documentation impact, workflow materialization, non-stable merge actor policy, whitespace, and red-list token patterns, then emits the exact `speculoos` check consumed by the Pullfrog coordinator. The destination guard blocks provider remediation from modifying this validator, the Pullfrog controller scripts, its shell validator, or the executable workflow-policy tests at both candidate sealing and publication. The hosted gate does not fetch the private Speculoos source repository or require a cross-repository credential. It excludes `main` and `master` targets and has no write or provider credential.

Under the current policy, workflow-maintenance automation creates PR branches from `dev`, cross-repo divergence review is delivered on the update PR as a managed comment by default rather than as committed review-doc files, and cross-repo updater runs that need to clone, branch, or open PRs in consumer repositories should be configured with `ELEVATED_GITHUB_TOKEN` rather than relying on the built-in `GITHUB_TOKEN`.
