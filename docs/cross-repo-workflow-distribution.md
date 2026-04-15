# Cross-repo workflow distribution draft

Status: draft

## Goal

Define the preferred cross-repo distribution model for workflow assets stored in this repository.

The current preferred direction is **Option B**:
- keep reusable workflows and starter templates in this shared repo as the canonical source library
- let consumer repos copy starter templates into their own `.github/workflows/`
- propagate upstream starter/reusable workflow updates through automated PRs or a controlled sync workflow, rather than relying on static copies forever

## Core principles

- `templates/reusable-workflows/` are shared engines
- `templates/starter-workflows/` are portable wrapper templates for consumer repos
- `.github/workflows/` in this repo are local runtime and dogfooding copies
- environment-specific configuration should live in GitHub vars, secrets, and workflow inputs, not as hardcoded values in live workflow files
- workflow YAML should carry structure, triggers, permissions, concurrency, and reusable-workflow wiring
- consumer repos must keep local control over whether and when to adopt upstream changes

## Problem this draft is solving

A consumer repo can copy a starter workflow from this shared repo and start using it locally, but then drift begins:
- reusable workflow SHAs can change upstream
- starter workflow structure can change upstream
- docs and variable contracts can evolve upstream
- consumers may need updates without manually re-copying files by hand

The question is how to preserve:
- shared source of truth
- controlled rollout
- per-consumer autonomy
- immutable pinned refs where needed

## Recommended architecture

### Shared repo responsibilities

This repo remains the canonical source of truth for:
- reusable workflow implementations under `templates/reusable-workflows/`
- starter workflow templates under `templates/starter-workflows/`
- materialization rules for local runtime copies under `templates/repo-workflow-materialization-manifest.json`
- reusable-workflow SHA diffusion bindings under `templates/workflow-ref-sync-manifest.json`
- helper scripts and validation logic

### Consumer repo responsibilities

A consumer repo owns:
- its live `.github/workflows/` copies
- its GitHub vars and secrets
- its choice to accept or defer upstream workflow updates
- any explicitly documented local adaptations

### Distribution model

1. A starter workflow is authored in this shared repo.
2. A consumer repo copies that starter workflow into its own `.github/workflows/`.
3. The copied workflow pins the shared reusable workflow by SHA or another approved ref strategy.
4. When upstream workflow assets change, the consumer repo receives a proposed update through automation, ideally as a pull request.
5. The consumer repo reviews and merges the change, keeping human control.

## Why Option B is preferred

Compared with direct static copying only:
- consumers do not silently drift forever
- the shared repo remains the source library
- updates stay reviewable and reversible

Compared with fully centralized live serving only:
- consumers keep local control over adoption timing
- repos can keep their own triggers, permissions, or local wrappers when needed
- GitHub vars and secrets stay local to the consumer repo

## Update propagation model

The preferred first-class update mechanism is:
- **automated PR creation into consumer repos**

That PR flow should:
- detect which consumer repos use which shared starter templates
- update the consumer repo's live workflow files when upstream source assets change
- update pinned reusable-workflow SHAs when needed
- keep changes narrow and reviewable
- avoid direct unreviewed pushes into consumer repos by default

## Candidate implementation strategies

### Strategy 1, updater workflow in the shared repo

The shared repo maintains a registry of consumer repos and managed workflow targets.

When a shared starter or reusable workflow changes:
- a workflow in this repo computes impacted consumers
- it opens PRs in those consumer repos with the necessary file updates

Pros:
- central source of truth
- easy to reason about rollout from one place

Cons:
- needs cross-repo auth and a maintained consumer registry

### Strategy 2, pull-based sync workflow in each consumer repo

Each consumer repo has a sync workflow or script that checks for upstream shared workflow updates and opens a local PR.

Pros:
- consumers keep explicit ownership
- simpler permission model in some setups

Cons:
- duplicated sync logic across many repos
- harder to enforce consistent behavior

### Strategy 3, managed install/update script

A shared script installs or refreshes workflow assets in a consumer repo on demand, locally or in CI, then opens a PR.

Pros:
- deterministic and scriptable
- good for local or semi-automated rollout

Cons:
- not as automatic by default unless paired with a scheduler

## Recommended first implementation

Start with a **shared-repo updater workflow** plus a simple registry.

### First phase scope

Build a narrow first version that:
- tracks a small set of consumer repos
- manages a small set of starter workflows
- opens PRs rather than pushing directly
- updates only workflow files and directly related metadata
- validates resulting workflow syntax before opening the PR

### Minimal required data model

The shared repo likely needs a manifest or registry that says:
- consumer repo slug
- branch to target
- which starter templates are installed there
- which local workflow paths they map to
- whether local divergence is allowed or blocked
- optional local variable/secret contract notes

## Rules for consumer-facing files

A consumer live workflow should ideally contain:
- trigger configuration
- permissions
- concurrency
- call into a pinned reusable workflow ref
- inputs or pass-through wiring

A consumer live workflow should ideally not contain:
- hardcoded secrets
- machine-specific paths
- per-user values
- hidden environment assumptions that belong in vars or secrets

## Versioning stance

Default recommendation:
- keep reusable workflow calls pinned to immutable SHAs for safety and reproducibility
- use automation to propose SHA bumps through PRs

Possible later variant:
- support stable tags like `@v1` for consumers that prefer looser updates

## Open questions still to resolve

- what registry format should describe consumer repos and installed workflow targets?
- should the update automation live only in the shared repo, or also optionally in consumers?
- how should local consumer modifications be detected and handled?
- should update PRs be batched or one-template-per-PR?
- should starter template updates and reusable SHA bumps always ship together when both changed?
- what is the minimum auth model for safe cross-repo PR creation?

## Suggested next drafting step

Turn this draft into a more concrete implementation proposal covering:
1. registry schema
2. updater workflow trigger rules
3. PR creation behavior
4. divergence policy for consumer repos
5. validation and rollback behavior
