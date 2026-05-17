---
name: github-pr-preflight
description: Use this skill before drafting, creating, or updating GitHub pull requests, especially for public or public-intended repositories. Apply it when preparing PR titles/bodies, running pre-PR checks, using gh pr create/edit, or ensuring branch diffs and PR prose do not leak private names, sensitive context, local paths, URLs, tokens, or internal incident details. Do not use it for code review, CI debugging, issue triage, or non-GitHub merge requests.
metadata:
  openclaw:
    emoji: "🛡️"
    requires:
      bins: ["git", "gh"]
---

# GitHub PR Preflight

## Goal

Create or prepare GitHub pull requests only after the branch diff **and** PR title/body are safe to publish. This skill exists because PR prose is often drafted from private chat context even when the committed diff is clean.

## Use this skill for

- drafting PR titles and bodies;
- creating PRs with `gh pr create`;
- editing PR descriptions with `gh pr edit`;
- final public-safety checks before opening a PR;
- converting private task context into public, technical PR language.

Do not use this skill for generic code review, CI troubleshooting, or branch synchronization unless the next action is PR preparation.

## Required inputs

Gather or infer:

- repo path;
- base branch, usually `dev` or `main`;
- head branch;
- target repo/remote;
- whether the repository is public, private, unknown, or public-intended;
- whether the user wants a draft only or an actual PR creation/edit.

Treat unknown visibility as public-intended.

## Required workflow

1. **Inspect branch state**
   - Confirm the current branch and target base.
   - Confirm the branch is based on the intended upstream base or report drift.
   - Check `git status --short --branch`.

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
   - Scan the PR prose with the same red-list mindset as the diff.
   - If prose contains private context, rewrite and re-scan before calling GitHub.

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

## Recommended PR body shape

```markdown
## Summary

- Technical change 1
- Technical change 2

## Validation

- Command/check that passed
- Public-safety scan passed: no private names, URLs, tokens, local paths, or case-specific details in the branch diff or PR prose
```

Optional sections:

- `## Notes` for public implementation constraints only.
- `## Follow-up` for non-sensitive next steps.

Avoid sections named `Context` unless the context is fully public and repo-relevant. Private motivation belongs in chat or local memory, not in the PR.

## Useful commands

```bash
# Branch and diff checks
git status --short --branch
git fetch origin <base>
git merge-base --is-ancestor origin/<base> HEAD
git diff --check origin/<base>...HEAD
git diff --name-only origin/<base>...HEAD
git diff --stat origin/<base>...HEAD

# Conservative red-list scan over diff
git diff origin/<base>...HEAD | grep -Ei 'token|secret|password|cookie|oauth|private key|signed url|trycloudflare|ngrok|/Users/|/home/|email|phone|tax|medical|patient|passport|invoice|customer' || true

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
- gate decision: `ready`, `needs-rewrite`, or `blocked`.

When creating or editing a PR, also return:

- PR URL;
- whether the diff gate passed;
- whether the PR prose gate passed.
