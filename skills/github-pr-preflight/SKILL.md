---
name: github-pr-preflight
description: Use this skill before drafting, creating, or updating GitHub pull requests, especially for public or public-intended repositories. Apply it when preparing PR titles/bodies, running pre-PR checks, verifying that work is on a dedicated feature branch from the current upstream base, using gh pr create/edit, or ensuring branch diffs and PR prose do not leak private names, sensitive context, local paths, URLs, tokens, or internal incident details. Do not use it for code review, CI debugging, issue triage, or non-GitHub merge requests.
metadata:
  openclaw:
    emoji: "🛡️"
    requires:
      bins: ["git", "gh"]
---

# GitHub PR Preflight

## Goal

Create or prepare GitHub pull requests only after the branch diff **and** PR title/body are safe to publish. This skill exists because PR prose is often drafted from private chat context even when the committed diff is clean.

Treat the PR title and body as public artifacts from the first draft, not only at `gh pr create` time. A sanitized draft shown to the user must pass the same PR prose red-list gate as a PR that will be published.

## Use this skill for

- drafting PR titles and bodies;
- creating PRs with `gh pr create`;
- editing PR descriptions with `gh pr edit`;
- final public-safety checks before opening a PR;
- enforcing a dedicated feature branch from the fetched upstream base before PR creation;
- converting private task context into public, technical PR language.

Do not use this skill for generic code review, CI troubleshooting, or branch synchronization unless the next action is PR preparation.

## Required inputs

Gather or infer:

- repo path;
- base branch, usually `dev` or `main`;
- head branch;
- target repo/remote;
- expected branch hygiene policy, normally dedicated head branch from current `origin/<base>`;
- whether the repository is public, private, unknown, or public-intended;
- whether the user wants a draft only or an actual PR creation/edit.

Treat unknown visibility as public-intended.

## Required workflow

1. **Enforce branch hygiene**
   - Fetch the target upstream base before deciding whether the branch is current: `git fetch origin <base>`.
   - Confirm the current branch and target base.
   - Require a dedicated head branch for the logical change. Do not prepare a PR directly from `dev`, `main`, `master`, a release branch, or the target base branch.
   - Confirm the dedicated branch was created from the current upstream base head, or at least contains it: `git merge-base --is-ancestor origin/<base> HEAD`.
   - If the branch is missing, stale, or based on an old base, report drift and stop unless the user explicitly authorizes branch creation, rebase, or recreation.
   - Check `git status --short --branch` and stop on uncommitted changes unless they are intentionally part of the PR.

2. **Review the public diff**
   - Run `git diff --check <base>...HEAD`.
   - List changed files with `git diff --name-only <base>...HEAD`.
   - Inspect the diff for red-list content before PR creation.

3. **Draft public-safe PR prose**
   - Explain the technical change, not the private user story that caused it.
   - Use generic context such as “validated during a recent workflow” instead of naming people, customers, documents, locations, private projects, or sensitive cases.
   - Do not include transient URLs, local filesystem paths, tokens, private filenames, session IDs, or internal logs.

4. **Audit the PR title/body as publishable content**
   - Save the proposed title/body to a temporary file or otherwise inspect it as text.
   - Run a named **PR prose red-list gate** before showing the draft to the user and again before publishing if the prose changed.
   - Scan the PR prose with the same red-list mindset as the diff.
   - Treat names from chat, private task motivation, local workspace details, phone numbers, account IDs, file paths, incident specifics, and internal operational history as unsafe unless they are intentionally public and necessary for the repository.
   - If prose contains private context, rewrite and re-scan before showing the draft, calling GitHub, or saving it as a reusable PR body.

5. **Create or update the PR only after both gates pass**
   - If the user asked only for a draft, return the sanitized title/body and stop.
   - If PR creation/editing is authorized, use `gh pr create` or `gh pr edit` with `--body-file` to avoid shell quoting mistakes.
   - After creation/editing, report the PR URL and the checks that passed.

## Red-list gate

Block PR creation/editing when the diff or PR prose contains:

- secrets, API keys, access tokens, OAuth tokens, cookies, passwords, private keys;
- real personal/customer/patient/family names unless clearly public and intentionally part of the repo;
- financial, medical, legal, tax, or identity-document details from a real case;
- private filenames, document titles, local paths, hostnames, IPs, tunnel URLs, or signed URLs;
- private email addresses, phone numbers, account IDs, tenant IDs, or cloud project identifiers;
- screenshots/log excerpts/transcripts that may contain private content;
- internal incident narratives that are not needed to understand the public technical change.

If a red-list item is found only in the PR prose, rewrite the prose; do not change the code just to mask a prose issue. If it is in the diff, stop and remediate the branch before creating the PR.

## PR prose red-list gate

This gate is mandatory for every PR draft, creation, or edit in a public, public-intended, or unknown-visibility repository.

Minimum procedure:

1. Write the proposed title/body to a temporary file.
2. Scan the file for red-list indicators.
3. Manually inspect the file for private motivation that keyword scans can miss.
4. Rewrite any private context into public technical language.
5. Re-run the scan after every rewrite.
6. Only then show the draft to the user or pass it to `gh pr create` / `gh pr edit`.

Default rewrite rules:

- Replace real user/customer/patient/family names with generic phrases such as `the workflow`, `the repository`, `the operator`, or `a recent validation pass`.
- Replace private motivation such as `requested by <person>` with public motivation such as `tightens the workflow` or `documents the expected behavior`.
- Remove chat-derived context that is not needed to understand the technical change.
- Remove local paths, machine names, account identifiers, cloud project IDs, phone numbers, emails, private URLs, and session IDs.
- Keep validation commands and changed-file summaries when they are public-safe.

Suggested backstop scan for a PR body file:

```bash
grep -En '([A-Z][a-z]+ [A-Z][a-z]+|/Users/|/home/|\+?[0-9][0-9 .-]{7,}|@[A-Za-z0-9_.-]+\.[A-Za-z]{2,}|token|secret|password|cookie|oauth|private key|signed url|trycloudflare|ngrok|customer|patient|passport|invoice|tax|medical|legal)' /tmp/pr-body.md || true
```

The scan is intentionally broad and may false-positive. A false positive is acceptable; a private PR body is not.

## Dedicated branch gate

For shared repositories and public-intended work, PR preparation must happen from a dedicated feature branch based on the current upstream base head. The normal starting sequence is:

```bash
git fetch origin <base>
git checkout -B feat/<purpose> origin/<base>
```

Only use `git checkout -B` when creating or safely recreating a branch with no uncommitted or unpushed work that would be lost. If work already exists on a branch, validate ancestry with `git merge-base --is-ancestor origin/<base> HEAD` and stop for an explicit rebase/recreate decision if the branch is stale.

Block PR creation when:

- the head branch is the same as the base branch;
- the head branch is `dev`, `main`, `master`, or a release/integration branch;
- the branch does not contain the current `origin/<base>` and no rebase/recreate decision has been approved;
- multiple unrelated logical changes are mixed into one branch.

## Recommended PR body shape

```markdown
## Summary

- Technical change 1
- Technical change 2

## Validation

- Command/check that passed
- Branch diff red-list gate passed: no private names, URLs, tokens, local paths, or case-specific details found
- PR prose red-list gate passed: title/body contain only public, technical repository context
```

Optional sections:

- `## Notes` for public implementation constraints only.
- `## Follow-up` for non-sensitive next steps.

Avoid sections named `Context` unless the context is fully public and repo-relevant. Private motivation belongs in chat or local memory, not in the PR.

## Useful commands

```bash
# Fresh feature branch for new PR work.
# Only run this before starting work, or after confirming recreation is safe.
git fetch origin <base>
git checkout -B feat/<purpose> origin/<base>

# Branch and diff checks for an existing PR branch
git fetch origin <base>
git status --short --branch
git branch --show-current
git merge-base --is-ancestor origin/<base> HEAD
git diff --check origin/<base>...HEAD
git diff --name-only origin/<base>...HEAD
git diff --stat origin/<base>...HEAD

# Conservative red-list scan over diff
git diff origin/<base>...HEAD | grep -Ei 'token|secret|password|cookie|oauth|private key|signed url|trycloudflare|ngrok|/Users/|/home/|email|phone|tax|medical|patient|passport|invoice|customer' || true

# Mandatory PR prose red-list gate before showing or publishing a draft
grep -En '([A-Z][a-z]+ [A-Z][a-z]+|/Users/|/home/|\+?[0-9][0-9 .-]{7,}|@[A-Za-z0-9_.-]+\.[A-Za-z]{2,}|token|secret|password|cookie|oauth|private key|signed url|trycloudflare|ngrok|customer|patient|passport|invoice|tax|medical|legal)' /tmp/pr-body.md || true

# Create PR from sanitized body file
gh pr create --base <base> --head <branch> --title "<title>" --body-file /tmp/pr-body.md
```

`grep` is only a backstop. Manual review of the title/body is mandatory.

## Output expectations

When preparing a PR, return:

- base/head branches;
- sanitized title;
- sanitized body;
- validation performed;
- branch hygiene gate result;
- branch diff red-list gate result;
- PR prose red-list gate result;
- gate decision: `ready`, `needs-rewrite`, or `blocked`.

When creating or editing a PR, also return:

- PR URL;
- whether the diff gate passed;
- whether the PR prose gate passed.
