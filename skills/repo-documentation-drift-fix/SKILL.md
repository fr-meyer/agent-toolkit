---
name: repo-documentation-drift-fix
description: Use this skill when the user needs repository documentation updated to match changed code or behavior. Apply it when requests involve fixing README drift, updating docstrings, refreshing usage docs, or correcting comments after code changes. Do not use it for broad documentation audits, generic copyediting unrelated to code changes, or large standalone documentation projects.
---

# Repo Documentation Drift Fix

## Goal

Keep repository documentation truthful and locally synchronized with changed code or behavior before commit.

## Use this skill for

- updating README usage or configuration sections after code changes
- fixing public API docstrings after interface or behavior changes
- updating comments when invariants or edge-case behavior changed
- making small, direct documentation updates that belong with the code change

## Do not use this skill for

- broad docs-readiness audits
- full documentation rewrites
- style-only copyediting unrelated to changed behavior
- inventing unsupported docs for ambiguous features

## Required inputs

Gather what is available:

- `repo_path`
- changed files or change summary
- affected behavior, API, or configuration
- documentation scope (`readme`, `docs`, `docstrings`, `comments`, `mixed`)

## Default approach

1. Identify the changed behavior.
2. Find the nearest docs that now drift from reality.
3. Update only the directly affected docs.
4. Keep the update truthful, local, and proportional to the code change.

## Update priorities

- README and quick-start content when user-facing behavior changed
- docs/reference pages when usage or configuration changed
- docstrings when public interfaces or behavior changed
- comments when implementation assumptions, invariants, or edge cases changed

## Validation

Before finishing, verify:

- docs match the changed behavior
- no unsupported claims were introduced
- comments explain non-obvious intent rather than narrating code
- the update stays local and does not balloon into a rewrite unless explicitly requested

## Gotchas

- not every code change requires README edits
- comments should explain why, invariants, or edge cases, not obvious operations
- do not turn a small code change into a full docs rewrite
- if the documentation need is broad or unclear, report that instead of guessing

## Portability notes

- prefer project-specific terminology over generic rewrite language
- keep changes close to the affected behavior and public surface area
- use audit skills separately when the user wants a broader readiness review
