---
name: repo-documentation-audit
description: Use this skill when the user needs to review or improve a repository's README, user-facing docs, public API docs/docstrings, or code comments. Apply it when requests involve documentation quality, onboarding clarity, public reference coverage, comment usefulness, or publishability/readiness checks for a repo. Do not use it for secret scanning, broad non-documentation code review, or generic prose editing unrelated to repository documentation.
---

# Repo Documentation Audit

## Goal

Evaluate repository documentation quality and publishability clarity across README content, user-facing documentation, public API docs/docstrings, and implementation comments.

This skill is documentation-focused and advisory by default.

## Use this skill for

- README quality and onboarding audits
- API docs/docstring completeness checks for public surfaces
- code comment usefulness checks (why/invariants/edge cases)
- docs readiness checks before sharing a repo publicly
- producing prioritized documentation improvement plans

## Do not use this skill for

- secret/privacy exposure scanning
- dependency/security vulnerability audits
- generic code review that is not primarily about documentation
- legal/compliance analysis beyond doc clarity

## Required inputs

Gather what is available:

- `repo_path`
- target scope (`full-repo`, `changed-files-only`, or explicit file list)
- publishability context (`internal`, `public-intended`, `already-public`)
- optional language/style conventions (if provided by user/project)

If scope is unclear, default to `changed-files-only` when a pending diff exists, otherwise `full-repo`.

## Workflow

1. Identify documentation artifacts in scope:
   - `README*`
   - docs directory files (`docs/`, `reference/`, equivalents)
   - public API doc sources/docstrings (language-specific)
   - notable inline/block comments in changed implementation files
2. Evaluate each artifact type against fit-for-purpose criteria:
   - README: value proposition, quick start, prerequisites, usage, help/license pointers
   - API docs/docstrings: purpose, inputs/outputs, failure modes, examples, caveats
   - comments: non-obvious intent/invariants/edge cases, not line-by-line narration
3. Classify findings by severity:
   - `critical`: blocks safe comprehension or causes high misuse risk
   - `major`: materially harms onboarding/usage quality
   - `minor`: polish or consistency issues
4. Produce an improvement plan prioritized by impact and effort.
5. If asked for rewrite help, provide ready-to-apply draft text snippets.

## Output format

Return a concise structured report:

```yaml
scope:
verdict: # ready | needs-improvements | not-ready
summary:
critical_findings:
major_findings:
minor_findings:
priority_actions:
suggested_patches:
notes:
```

Output rules:
- If no issues for a category, return `[]`.
- Keep `priority_actions` to the top 3-7 highest-value items.
- Treat findings as advisory unless caller explicitly requests gating behavior.

## Gotchas

- Do not confuse documentation quality issues with security red-list issues.
- Do not enforce one language ecosystem's doc style as universal.
- Do not require exhaustive docs for internal-only prototypes unless asked.
- Do not mark "no tutorial" as critical if a clear quick start exists.
- For comments, prioritize "why" over repeating obvious code operations.

## Portability notes

- Keep heuristics provider-agnostic and language-aware.
- Favor repository evidence over assumptions.
- If style guides exist, prefer project-specific rules over generic advice.
