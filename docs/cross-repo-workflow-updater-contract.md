# Cross-repo workflow updater logic contract

Status: draft logic contract

Related documents:
- `docs/cross-repo-workflow-distribution.md`
- `docs/cross-repo-workflow-distribution-spec.md`
- `templates/cross-repo-workflow-distribution-manifest.json`

## 1. Purpose

This document defines the runtime behavior contract for the shared-repo updater that proposes starter-workflow updates into consumer repositories.

It answers:
- what inputs the updater reads
- what decisions it makes
- when it opens a PR
- when it skips, fails, or requests manual review
- what outputs and summaries it must produce

## 2. Updater responsibility boundary

The updater is responsible for:
- reading the cross-repo distribution manifest
- determining which consumer repos are impacted by shared starter-template changes
- resolving the branch to target in each consumer repo
- generating exact-managed candidate file updates
- detecting divergence
- validating rendered results
- opening at most one reviewable PR per consumer repo per run
- emitting a machine-readable and human-readable run summary

The updater is not responsible for:
- changing canonical source templates in this shared repo
- fixing consumer-specific vars or secrets
- force-overwriting diverged consumer workflow files
- auto-merging consumer PRs in V1
- auto-rollback after merge in V1

## 3. Required inputs

The updater must accept these inputs.

### 3.1 Shared source context

Required:
- `sharedRepository`
- `sourceBranch`
- `sourceCommitSha`

Optional:
- `previousSourceCommitSha`
- `manualConsumerFilter[]`
- `manualStarterTemplateFilter[]`
- `manualSourceCommitOverride`
- `dryRun`

## 3.2 Manifest input

Required file:
- `templates/cross-repo-workflow-distribution-manifest.json`

The updater must load and validate:
- manifest schema version
- consumer entries
- managed bindings

## 3.3 Repository access input

The updater must have credentials that can:
- read this shared repo at the relevant source commit
- read each consumer repo metadata
- read and checkout each target consumer repo branch
- push an update branch or fork branch
- open a PR in the consumer repo

Required local tooling for the current V1 implementation:
- `git`
- `python3`
- at least one working PR provider/auth path:
  - `gh`, or
  - a GitHub token discoverable via environment variable, or
  - `gh auth token`, or
  - `.netrc`, or
  - embedded HTTPS remote credentials

`gh` is the easiest path to install and operate, but it is no longer the only non-manual PR-opening path.

## 4. Required invariants

Before updating any consumer repo, the updater must assume or verify:
- the shared repo is already internally converged
- starter templates are the canonical consumer-facing distribution units
- the manifest is syntactically valid
- every binding references a starter template under `templates/starter-workflows/`
- every binding target path is under `.github/workflows/`

If these invariants do not hold, the updater must fail the affected work and report why.

## 5. Run phases

The updater run is divided into ordered phases.

### Phase 1. Load and validate manifest

Steps:
1. read `templates/cross-repo-workflow-distribution-manifest.json`
2. validate `schemaVersion`
3. validate every consumer entry
4. validate every enabled binding

Failure behavior:
- if the manifest itself is invalid, abort the whole run
- if one consumer entry is invalid but others are valid, V1 may either abort globally or mark the invalid consumer as failed and continue; preferred behavior is per-consumer failure where possible

### Phase 2. Determine changed starter templates

Normal push-triggered mode:
1. compute changed files between `previousSourceCommitSha` and `sourceCommitSha`
2. keep only paths under `templates/starter-workflows/`
3. if the changed set is empty, exit cleanly with `reason=no_impacted_templates`

Manual mode:
- if `manualStarterTemplateFilter[]` is provided, use that set as the effective candidate set
- if `manualSourceCommitOverride` is provided, use that commit as the source state

### Phase 3. Resolve impacted bindings

For each consumer in the manifest:
1. skip if filtered out by manual consumer filter
2. ignore disabled bindings
3. keep bindings whose `starterTemplate` is in the effective changed-template set
4. if no bindings remain, mark the consumer as `not_impacted`

### Phase 4. Resolve target branch

For each impacted consumer repo:
1. if `baseBranch` exists on the consumer entry, use it
2. otherwise resolve the repo's default branch from repo metadata or remote HEAD
3. if default branch cannot be resolved, mark consumer as `branch_resolution_failed`

Contract:
- resolved branch name must be recorded in the run summary
- the updater must never guess silently beyond the available metadata

### Phase 5. Prepare consumer workspace

For each impacted consumer repo:
1. checkout the consumer repo
2. checkout the resolved target branch
3. create or reset a dedicated updater branch
4. ensure the workspace is clean before writing files

Recommended branch naming:
- `chore/sync-shared-workflows-<shortsha>`

If repository checkout or branch creation fails:
- mark consumer as `checkout_failed`
- continue to other consumers when possible

### Phase 6. Render candidate file updates

For each impacted binding:
1. read the canonical starter template from the shared repo at `sourceCommitSha`
2. compute the target file path in the consumer repo
3. prepare exact replacement content
4. compare candidate content with current consumer file content

Result categories per binding:
- `no_change`
- `candidate_update`
- `target_missing` (still valid, may become a create action if binding expects managed presence)
- `render_failed`

V1 rendering rule:
- exact file replacement only
- no line-level merge logic
- no in-file consumer-specific interpolation layer

### Phase 7. Divergence detection

For each binding with a current-file/content mismatch:
1. compare the consumer target file against the current canonical starter template
2. if it does not match, compare it against historical revisions of that same registered starter template in the shared repo
3. if the consumer file matches a historical shared revision, classify it as a safe managed `candidate_update`
4. otherwise, if divergence policy is `exact`, classify it as `diverged`
5. do not stage an overwrite for diverged bindings

V1 implemented divergence heuristic:
- safe managed outdated file = exact content match to a historical revision of the registered starter template
- diverged file = no exact match to the current or any historical revision of the registered starter template

Contract:
- divergence must be explicit in the run summary
- the updater must not silently replace diverged exact-managed files

## 6. Binding-level decision matrix

For each binding, the updater must classify the outcome:

- `not_impacted`
- `no_change`
- `candidate_update`
- `diverged`
- `render_failed`
- `validation_failed`
- `staged_for_pr`
- `skipped_due_to_consumer_failure`

## 7. Consumer-level decision matrix

After evaluating all bindings for one consumer repo:

### Open PR
Open a PR when:
- at least one binding is `staged_for_pr`
- no blocking consumer-level failures exist
- validation succeeds for the staged result

### Skip cleanly
Skip without PR when:
- no binding is impacted
- all impacted bindings are `no_change`

### Manual review required
Do not open a normal update PR when:
- any impacted exact-managed binding is `diverged`
- no safe staged updates remain after divergence filtering

Preferred follow-up behavior:
- optionally open an **AI-assisted manual-review PR** instead of a normal sync PR
- if `manual_review_delivery=pr-comment` and an updater-owned PR for the same updater branch already exists, post or update the managed divergence comment there
- otherwise, fall back to opening a standalone manual-review PR rather than stopping at a dead-end `manual_review_required_no_pr` result
- that PR should present a review artifact, not a silent overwrite
- when confidence is high enough, it may include an explicitly labeled proposed normalization patch, but it must keep uncertainty visible rather than disguising adjudication as deterministic sync

### Failure
Mark consumer as failed when:
- branch resolution fails
- checkout fails
- rendering fails for all impacted bindings
- validation fails for the staged result
- PR creation fails

## 8. Validation contract

Validation happens after candidate changes are staged in the consumer workspace but before PR creation.

The updater must validate:
- resulting YAML parses correctly
- every updated target path is still under `.github/workflows/`
- each rendered file came from the registered starter template path
- expected pinned reusable-workflow `uses: ...@<sha>` refs remain present when required by the starter template
- no non-managed files were changed unintentionally by the updater

If validation fails:
- do not open a PR
- classify the consumer result as `validation_failed`
- include clear failure details in the run summary

## 9. PR creation contract

When a PR is opened, the updater must:
1. prepare a dedicated updater branch from the resolved target branch
2. commit only the staged managed workflow file changes, or commit only the diagnostic review artifact when operating in manual-review mode
3. push the updater branch
4. open one PR against the resolved target branch

V1 implementation path:
- local consumer clone required
- `git` is used for fetch, branch preparation, staging, commit, and push
- PR discovery/creation uses an automatic provider chain in this order:
  1. GitHub CLI (`gh`)
  2. GitHub REST API
  3. GitHub GraphQL API

### 9.1 AI-assisted manual-review PR mode

This mode is for cases where deterministic sync is blocked by divergence but a human-reviewable investigation PR is still useful.

Inputs to the AI review step should include:
- the registered starter template path
- the current consumer workflow file
- the bounded diff between them
- any pinned SHA differences
- any contract-level differences such as removed or added inputs, secrets, or passthrough fields
- the updater's current confidence and explicit doubts

The AI review output should contain these sections:
1. scope
2. verified diff facts
3. interpretation
4. confidence and doubts
5. recommendation

Allowed recommendations:
- normalize to the shared starter template now
- keep as intentional customization and remove from exact-managed scope
- adjudicate manually before any normalization PR

Contract rules for manual-review PR mode:
- do not present uncertain interpretation as settled fact
- separate deterministic evidence from inference
- make any proposed patch explicitly optional/reviewable
- make clear whether the PR is for discussion only or intended for merge
- do not hijack arbitrary human PRs for comment delivery; `pr-comment` mode may only reuse an updater-owned PR for the same updater branch
- when no updater-owned PR exists, fall back to a standalone manual-review PR

### 9.1.1 Manual-review artifact lifecycle

Default policy for manual-review artifacts such as divergence reports and optional normalization patches:
- treat them as temporary review scaffolding, not as permanent runtime assets by default
- make the artifact purpose explicit in the PR body
- keep them on the review branch while adjudication is in progress
- if normalization is approved, prefer a clean follow-up PR that changes the live `.github/workflows/` files directly and does not keep the review artifacts unless there is a specific archival reason
- if customization is intentional, prefer closing the review PR and changing manifest/policy treatment rather than merging artifact-only files into the long-term branch by accident

The updater should therefore frame these artifacts as evidence and proposal material, not as the desired long-term repository state.

## 9.2 Current PR opening dependency and automatic fallbacks

Current V1 implementation now uses an automatic fallback chain for PR discovery and creation:
1. `gh`
2. GitHub REST API
3. GitHub GraphQL API

Credential discovery for the API-based fallbacks currently tries, in order:
1. environment variables (`ELEVATED_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GITHUB_PAT`, `GITHUB_API_TOKEN`, `GITHUB_OAUTH_TOKEN`, `GITHUB_APP_TOKEN`)
2. embedded HTTPS remote credentials
3. `gh auth token`
4. `.netrc`

Installation note for macOS with Homebrew:
- `brew install gh`
- then authenticate with `gh auth login`

The main requirement is not specifically `gh`; it is the ability to reliably:
- detect an existing PR for the updater branch
- open a new PR against the resolved base branch
- return the PR URL and provider into the updater summary

A future first-class OpenClaw GitHub/PR tool would also be an acceptable provider path if one is later available.

PR title format:
- `chore(ci): sync shared workflows from fr-meyer/agent-toolkit@<shortsha>`

PR body must include:
- source repo and source commit
- resolved consumer target branch
- list of starter templates used
- list of consumer workflow paths updated
- previous and new pinned reusable-workflow SHAs when detectable
- validation summary
- explicit note that the PR is safe to revert if needed
- for manual-review PRs, explicit lifecycle guidance for any included review artifacts and what the expected follow-up path is after adjudication

## 10. Idempotency contract

For the same source commit and same consumer target branch:
- rerunning the updater should not create duplicate divergent changes
- rerunning after a successful no-change result should produce no PR
- rerunning after a previously opened equivalent PR may update the same updater branch/PR or detect that an equivalent PR already exists

V1 acceptable behavior:
- either update the existing updater branch for that consumer/source pair
- or detect an equivalent open PR and skip duplicate PR creation

## 11. Logging and summary contract

The updater must emit both:
- human-readable logs during execution
- a machine-readable run summary artifact

Recommended summary artifact path:
- `artifacts/cross-repo-workflow-updater-summary.json`

Recommended top-level summary shape:

```json
{
  "schemaVersion": "1.0.0",
  "sharedRepository": "fr-meyer/agent-toolkit",
  "sourceCommitSha": "<sha>",
  "previousSourceCommitSha": "<sha-or-null>",
  "dryRun": false,
  "consumers": [
    {
      "repo": "fr-meyer/zotero-docai-pipeline",
      "resolvedBaseBranch": "feature/package-cli-app",
      "status": "pr_opened",
      "bindings": [
        {
          "starterTemplate": "templates/starter-workflows/coderabbit-pr-comment-trigger.yml",
          "targetPath": ".github/workflows/coderabbit-pr-comment-trigger.yml",
          "status": "staged_for_pr"
        }
      ],
      "pullRequestUrl": "https://github.com/...",
      "pullRequestProvider": "rest+env:GITHUB_TOKEN",
      "message": "Updated 1 managed workflow file."
    }
  ]
}
```

## 12. Dry-run contract

When `dryRun=true`:
- perform manifest loading
- perform impact analysis
- resolve branches
- render candidate updates
- run divergence detection
- run validation where possible
- if configured, prepare the inputs that would feed AI-assisted manual-review mode
- do not push branches
- do not open PRs

Dry-run output must still include the full summary with statuses like:
- `would_open_pr`
- `would_skip`
- `would_require_manual_review`
- `would_open_manual_review_pr`

## 13. Failure handling contract

The updater must prefer per-consumer isolation.

Meaning:
- one consumer failure must not erase the results of other consumers
- each consumer should get an independent terminal status

Consumer terminal statuses should include at least:
- `not_impacted`
- `no_change`
- `pr_opened`
- `manual_review_required`
- `validation_failed`
- `branch_resolution_failed`
- `checkout_failed`
- `pr_creation_failed`

## 14. Rollback contract

Rollback behavior remains intentionally simple in V1.

Before merge:
- failed validation means no PR
- divergence means no normal overwrite PR

After merge:
- the rollback path is to revert the updater PR in the consumer repo

The updater must therefore ensure that:
- PRs are small and bounded
- PR descriptions clearly state source commit and changed files
- consumer maintainers can revert safely without guessing what changed

## 15. Security contract

The updater must not:
- force-push consumer default branches
- bypass branch protection
- mutate files outside declared managed bindings
- overwrite diverged exact-managed consumer workflow files silently

## 16. Recommended implementation split

A clean V1 implementation can be split into these components:

1. manifest loader and validator
2. changed-template detector
3. consumer impact resolver
4. base-branch resolver
5. consumer workspace preparer
6. exact renderer
7. divergence detector
8. validator
9. PR creator
10. summary writer

## 17. Minimum success definition for V1

The updater is considered correct enough for V1 when it can:
- detect starter-template changes
- identify impacted consumer bindings from the manifest
- resolve each consumer target branch, including default branch when omitted
- stage exact-managed workflow updates safely
- refuse unsafe overwrites on divergence
- validate the staged result
- open one bounded PR per impacted consumer repo
- emit a clear summary of what happened
