---
name: github-workflow-asset-library
description: Use this skill when the user needs to create, modify, reclassify, materialize, or document GitHub Actions workflows in a repository that treats workflows as canonical template assets under `templates/` and keeps live runtime copies under `.github/workflows/`. Apply it when requests involve `templates/reusable-workflows/`, `templates/starter-workflows/`, workflow materialization manifests, pinned `uses:` ref maintenance, or enforcing the rule that every live workflow should have a canonical template source. Do not use it for generic CI/CD authoring in repos that do not follow this source-library layout.
compatibility: Requires a repository that stores GitHub Actions workflow source assets under `templates/` and may use `templates/repo-workflow-materialization-manifest.json` and `templates/workflow-ref-sync-manifest.json`.
---

# GitHub Workflow Asset Library

## Goal

Help the agent safely create, modify, and maintain GitHub Actions workflows in repositories that use a source-library layout where canonical workflow sources live under `templates/` and live runtime copies live under `.github/workflows/`.

## Default approach

- Treat `templates/` as the source of truth.
- Classify workflow templates by role, not by where a rendered copy happens to run.
- Edit canonical template sources first, then materialize live `.github/workflows/` copies.
- Keep pinned reusable-workflow refs coherent with the authoritative reusable workflow commit they describe.
- Maintain both manifests explicitly: one for materialization, one for reusable-workflow SHA diffusion.
- Update local docs when the architecture or rule changes.

## Scope boundaries

Use this skill for:
- creating or modifying workflows in repos that use `templates/reusable-workflows/` and `templates/starter-workflows/`
- deciding whether a workflow belongs in `reusable-workflows` or `starter-workflows`
- introducing or updating `.github/workflows/` materialized copies from canonical templates
- updating `templates/repo-workflow-materialization-manifest.json`
- updating `templates/workflow-ref-sync-manifest.json` when starter templates or linked live workflows should track reusable workflow refs
- deciding whether SHA diffusion targets should include starter templates only, or starter templates plus linked live workflows
- documenting the workflow asset layout so later humans and agents can recover it

Do not use this skill for:
- generic GitHub Actions or CI/CD design in repos that do not use this source-library layout
- deployment strategy, release engineering, or branch policy decisions
- editing workflow consumers in unrelated repos unless the request is specifically about this layout pattern
- generic Git synchronization or unrelated documentation cleanup

## Workflow

1. Confirm the repo is using a workflow source-library layout.
2. Read repo-local workflow guidance if present.
3. Inspect the existing template folders, live workflow copies, and manifests.
4. Decide the workflow role before editing.
5. Edit the canonical template source under `templates/`.
6. Update materialization and ref-sync manifests if needed.
7. Re-materialize live `.github/workflows/` copies.
8. Update durable docs when the rule or architecture changed.
9. Validate that live copies match their canonical sources and that no stale references remain.

## Procedure

### 1. Confirm the layout

Look for the strongest available indicators:
- `templates/reusable-workflows/`
- `templates/starter-workflows/`
- `.github/workflows/`
- `templates/repo-workflow-materialization-manifest.json`
- `templates/workflow-ref-sync-manifest.json`
- repo docs describing workflow assets as source templates

If the repo does not clearly use this pattern, stop and fall back to normal workflow authoring rather than forcing the layout.

### 2. Read local guidance first

If present, read these before editing workflow assets:
- `AGENTS.md`
- `docs/workflow-authoring-rules.md`
- `docs/workflow-asset-library-layout.md`
- `README.md`

Treat repo-local workflow docs as the current behavior source of truth when they exist.

### 3. Classify by role

Use this rule:
- callable reusable workflows, typically with `on: workflow_call`, belong in `templates/reusable-workflows/`
- copy/adapt entrypoints and starter templates belong in `templates/starter-workflows/`
- every live `.github/workflows/` file should have a canonical template source under one of those two folders

Important nuance:
- a repo-local trigger workflow can still belong in `templates/starter-workflows/` when its canonical role is an entrypoint template that may be copied or adapted later
- do not create a third category unless the repo docs explicitly require it

### 4. Edit the canonical source first

When creating or modifying a workflow:
- create or update the canonical source file under `templates/`
- avoid treating `.github/workflows/` as the primary authoring location
- if a live runtime copy already exists, update the canonical source and re-materialize instead of hand-editing the rendered copy

### 5. Maintain the manifests

Update `templates/repo-workflow-materialization-manifest.json` when:
- a canonical template should materialize to `.github/workflows/`
- a live workflow target is renamed
- a materialized workflow is added or removed

Update `templates/workflow-ref-sync-manifest.json` when:
- starter templates should keep pinned reusable-workflow refs aligned
- linked live workflows should also keep pinned reusable-workflow refs aligned
- a reusable workflow source path changes
- a published `.github/workflows/...` path changes
- a target file is added to or removed from managed ref-sync scope

Treat the ref-sync manifest as the explicit binding table from:
- reusable workflow source
- to published workflow path
- to every target file that should receive SHA diffusion

### 6. Re-materialize and verify

After editing:
- run the repo's materialization mechanism if one exists
- verify each materialized `.github/workflows/` file matches its canonical source
- verify that references to renamed workflows were updated in manifests, docs, and calling workflows
- verify mapped starter templates and mapped linked live workflows still point at the correct reusable workflow path and commit/ref shape
- verify `shared_repository_ref` was updated too when that field exists in a mapped target

### 7. Update durable docs when needed

When the layout rule, classification rule, or authoring model changes:
- update repo docs that explain the workflow layout
- add or update an `AGENTS.md` or equivalent repo-local instructions file if future agents need recovery guidance
- keep the rule explicit enough that a future agent can reconstruct the model without relying on memory

## Gotchas

- Do not classify by where the file happens to execute locally. Classify by role.
- Do not hand-edit `.github/workflows/` as the only source if the repo uses template sources.
- Do not move a trigger entrypoint into `reusable-workflows` just because this repo runs it.
- Do not leave a live `.github/workflows/` file without a canonical template source.
- Do not rename a canonical workflow source without updating manifests, callers, and docs.
- Do not forget that reusable-workflow SHA diffusion is controlled separately from materialization.
- When a reusable workflow changes, decide explicitly whether diffusion should reach starter templates only, or starter templates plus linked live workflows.
- When a target pins a reusable workflow, keep the `uses: ...@<ref>` aligned, and keep `shared_repository_ref` aligned too when that field exists.

## Resources

Read only when needed:
- `references/layout-rules.md` — use when you need the compact canonical rule set and edit checklist
- `references/eval-prompts.json` — use when checking whether this skill's trigger boundary is too broad or too narrow

## Portability notes

- Prefer repo-local docs over bundled defaults when the repo already defines this layout.
- Keep the classification model product-light: the pattern is about canonical templates and materialized runtime copies, not about one specific CI provider beyond GitHub workflow paths.
- Do not assume a specific materializer script name unless the repo already defines one.
