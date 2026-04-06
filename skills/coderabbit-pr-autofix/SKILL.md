---
name: coderabbit-pr-autofix
description: "Use this skill when the user wants a CodeRabbit-only wrapper around an available autofix skill for the current branch’s open PR: collect unresolved CodeRabbit review threads, summarize them, and then run autofix in automatic mode with commit and push disabled. Do not use it for human review comments, generic PR review, approval-first workflows, or standalone fixing."
---

# CodeRabbit PR Autofix

## Goal

Provide a **thin CodeRabbit-only wrapper around an available `autofix` skill** for the current branch’s open PR.

This skill exists only to add:
- tighter PR scoping
- unresolved CodeRabbit-thread filtering
- automatic execution defaults
- no-commit / no-push defaults

This skill must **not** duplicate, replace, or broaden the main `autofix` workflow.

## Use this skill for

- unresolved CodeRabbit review threads on the current branch’s open PR
- users who want a CodeRabbit-only wrapper before running autofix
- automatic fixing without item-by-item approval
- workflows where commit and push must remain disabled

## Do not use this skill for

- human review comments
- non-CodeRabbit review comments
- resolved review threads
- generic PR review handling
- approval-first fix workflows
- commit or push workflows
- standalone bug fixing unrelated to unresolved CodeRabbit PR review threads
- replacing the broader `autofix` skill

## Dependency on `autofix`

This skill is intentionally a wrapper around `autofix`.

- Treat an available `autofix` skill as the **primary fixing workflow**.
- This skill adds **scope and execution defaults**, not a second implementation.
- If `autofix` is unavailable in the current environment, stop and report that this wrapper depends on it rather than reimplementing its full logic here.

## Default behavior

Unless the user explicitly overrides it, use these defaults:

- current git branch only
- current branch’s open PR only
- unresolved review threads only
- CodeRabbit-authored root comments only
- automatic fix application
- no approval loop
- no commit
- no push
- no PR comment posting

This skill is **non-interactive by default**. If the user wants an approval-based workflow, prefer `autofix` directly instead of this wrapper.

## Workflow

### 1. Verify current PR context

Before proceeding, confirm all of the following:

- the working directory is inside a git repository
- the current branch is known
- the current branch has an open PR
- the PR has unresolved review threads
- at least one unresolved review thread belongs to CodeRabbit

If any check fails, stop and explain the missing precondition briefly.

### 2. Collect unresolved CodeRabbit review threads only

For the current branch’s open PR:

- fetch review threads
- keep only unresolved threads
- keep only threads whose root comment author is CodeRabbit
- ignore resolved threads
- ignore human-authored review threads
- ignore non-CodeRabbit review feedback

Treat these identities as valid CodeRabbit matches when present:

- `coderabbitai`
- `coderabbit[bot]`
- `coderabbitai[bot]`

If no unresolved CodeRabbit review threads are found, stop and report that there is nothing for this wrapper to process.

### 3. Summarize the extracted issues

Before invoking the fixing workflow, produce a concise numbered summary of the unresolved CodeRabbit issues.

For each issue, include when available:

- issue number
- issue title or short description
- severity
- file path / location
- brief intended action

Preserve CodeRabbit’s original ordering when possible.

This summary is for visibility only. Do not wait for approval before continuing.

### 4. Route into the existing `autofix` workflow

After unresolved CodeRabbit issues have been collected and summarized:

- follow the available `autofix` workflow as the fixing engine
- preserve its parsing and fix-application logic
- do not fork or recreate that logic here

This wrapper narrows `autofix` to this operating mode:

- scope = current branch’s open PR only
- scope = unresolved CodeRabbit review threads only
- execution = auto-apply
- commit = disabled
- push = disabled

### 5. Auto-apply fixes

Run the `autofix` workflow in automatic mode.

- Apply clear fixes without waiting for approval.
- If an issue is ambiguous, risky, or under-specified, skip it and report it.
- Do not force speculative changes just to clear an item.

### 6. Final report

At the end, provide a concise summary that includes:

- number of unresolved CodeRabbit issues found
- number of fixes applied
- number of issues skipped
- changed files
- short reasons for skipped items

Do not commit changes.
Do not push changes.
Do not post PR comments unless the user explicitly asks.

## Scope boundary

This skill is a **CodeRabbit-only unresolved-PR wrapper around `autofix`**.

That means:

- narrower than `autofix`
- dependent on `autofix`
- non-interactive by default
- not a general review skill
- not a general fixing skill
- not a commit/push workflow

If the request is broader than unresolved CodeRabbit review threads on the current branch’s open PR, use `autofix` directly instead of this wrapper.

## Gotchas

- Do not widen scope beyond the current branch’s open PR.
- Do not include resolved threads.
- Do not include human review comments.
- Do not introduce an approval loop by default.
- Do not commit or push.
- Do not reimplement the full `autofix` logic in this skill.
