---
name: public-repo-red-list-remediation
description: Use this skill when the user needs to automatically remediate blocker findings from a public-repo safety review before commit or push. Apply it when requests involve removing, redacting, neutralizing, or excluding secrets, private data, internal-only material, or other public red-list content from a pending changeset. Do not use it for generic code review, broad security hardening, or non-publication-related refactoring.
---

# Public Repo Red List Remediation

## Goal

Transform a pending changeset so it no longer contains blocker content that is unsafe to commit or push to a public repository.

## Use this skill for

- removing or redacting secrets before commit
- replacing risky sample values with placeholders or env-var references
- excluding unsafe files from the pending commit
- cleaning logs, dumps, exports, or internal-only docs from a public-facing changeset
- rewriting public PR prose, release notes, or task metadata that copied private context into public-facing surfaces
- preparing history rewrite or hosted-artifact escalation when sensitive content already reached a public PR patch/diff

## Do not use this skill for

- generic vulnerability remediation
- large architectural rewrites
- broad compliance programs
- deciding whether content is risky in the first place without an audit signal

## Required inputs

Gather what is available:

- `repo_path`
- remediation scope (`staged-only`, `pending-changes`, `explicit-files`)
- findings from `public-repo-red-list-audit`, if available
- repository visibility context (`public`, `private`, `unknown`, `public-intended`)

## Default approach

1. Identify the exact blocker content.
2. Prefer the smallest effective remediation.
3. Re-run the red-list audit after remediation.
4. Proceed only when blocker findings are cleared.

## Remediation order

1. Remove the risky content entirely.
2. Redact the risky fragment.
3. Replace it with a placeholder, env-var reference, or TODO-safe stub.
4. Exclude the risky file or fragment from the pending commit.

Prefer temporary breakage over committing dangerous public red-list content.

## Public Attribution Rule

Do not redact intentionally public attribution solely because it is a personal name.

Preserve names and GitHub noreply email addresses in:

- Git author or committer metadata
- `Co-authored-by` trailers
- copyright or license notices
- package/project author metadata
- public maintainer or README attribution

Clean the private context around a name instead. Still remove or generalize local paths, local usernames, workspace names, private runtime names, private memory references, private project/property/customer context, and chat-derived notes such as `<person> wants...` when they do not belong in public metadata.

## Hosted PR Artifacts

For public or public-intended GitHub repositories, remediation is not complete until hosted PR artifacts are also checked when a PR exists.

- Re-scan the PR title/body after editing.
- Fetch and scan the generated PR `.patch` or `.diff` endpoint before merge.
- If a public PR patch/diff contains sensitive context, rewrite the branch before merge when possible.
- If the PR is already closed/merged and GitHub retains the leak through read-only `refs/pull/*`, report that normal remediation is insufficient and recommend a proportionate escalation such as GitHub Support purge, temporary repository privacy, or repo recreation for severe cases.

## Validation

Before finishing, verify:

- blocker content is no longer present in the pending commit scope
- replacements do not preserve the original secret/value
- excluded files are truly excluded from the commit
- the follow-up red-list audit passes or remaining blockers are clearly reported
- any existing public PR body and generated `.patch`/`.diff` views are clean, or unremovable hosted artifacts are explicitly reported

## Gotchas

- deleting a secret in a later commit does not undo exposure if it was already committed
- rewriting branch history does not necessarily clean closed PR patch/diff views hosted by GitHub
- test fixtures and docs often hide live values
- "internal-only but harmless" is not a safe assumption for public repos
- do not silently leave risky content staged after partial remediation
- do not remove public attribution metadata just to hide a private-context finding; remove the private context instead

## Portability notes

- keep remediation hosting-provider agnostic
- prefer the smallest truthful remediation over large cleanup rewrites
- if a file must be excluded, make that explicit in the final report
