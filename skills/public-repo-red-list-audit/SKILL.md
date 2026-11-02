---
name: public-repo-red-list-audit
description: Audit repository content, history, and metadata for public-safety leaks before commit, push, release, or publication.
---

# Public Repo Red List Audit

## Goal

Prevent accidental publication of sensitive or non-public material by auditing repository content, Git history, and hosting metadata before commit, push, release, or publication.

This skill is safety-focused and should be treated as a blocking gate when high-risk findings exist.

## Use this skill for

- pre-commit or pre-push checks for public repositories
- audits of staged/unstaged/untracked changes for public safety
- full repository audits before making a repository public
- public homepage, README, documentation, release note, package metadata, topic, and description checks
- "is this repo safe to make public?" assessments
- identifying red-list content in files, diffs, logs, exports, configs, docs, Git history, and hosting metadata
- checking GitHub PR titles/bodies and generated `.patch`/`.diff` views for repositories that are public or public-intended

## Do not use this skill for

- generic code quality/style reviews
- documentation clarity audits
- architecture improvement recommendations unrelated to exposure risk
- resolving merge conflicts or Git workflow strategy

## Required inputs

Gather what is available:

- `repo_path`
- scope (`staged-only`, `pending-changes`, `explicit-files`, `current-tree`, `full-history`, `full-repo`)
- remote visibility context (`public`, `private`, `unknown`, `public-intended`)
- hosting metadata if relevant or discoverable:
  - repository name
  - description
  - homepage URL
  - topics
  - package metadata
  - release metadata
  - project/App homepage text
- optional policy overrides from user/org

If visibility is unknown and a push is requested, treat risk conservatively and run the audit.

For a repository that is already public or about to become public, prefer `full-repo` unless the user explicitly narrowed the question. `full-repo` means current tree plus full reachable Git history plus hosting metadata.

When a GitHub PR already exists for a public or public-intended repository, treat the PR body and generated PR `.patch`/`.diff` endpoints as public hosting metadata. A clean local tree is not enough if the hosted PR patch still exposes private context.

## Red-list categories

Treat the following as high-priority risk classes:

1. Secrets and credentials
   - API keys, access tokens, passwords, private keys, signing keys, live connection secrets
2. Private or regulated data
   - real personal/customer data, financial/health/legal-sensitive records, production exports
3. Internal-only operational/security material
   - sensitive runbooks, internal architecture/network details, privileged procedures, deployment topology, access paths, hostnames, private IPs, SSH aliases, forced-command details, and token handling internals not intentionally public
4. Personal/context disclosure beyond the public purpose
   - unnecessary non-public personal/context disclosure, private project names, internal runtime names, local usernames, home directory paths, machine names, workspace names, account aliases, and implementation details that identify the owner or operating environment without adding public trust value
   - do **not** flag intentionally public attribution names solely because they are personal names when they appear in author, committer, `Co-authored-by`, copyright, license, package-author, maintainer, or profile-backed project metadata
5. Risky generated artifacts
   - logs, dumps, backups, support bundles that may contain tokens/data
6. Non-approved proprietary or internal business material
   - content not intentionally approved for public disclosure

## Severity guidance

- `blocker`: live secret/credential, private key, regulated/private data, private token-bearing log, or any public history exposure that cannot be remediated by editing only the current tree.
- `review-required`: unnecessary personal/context disclosure, internal runtime names, host paths, private architecture descriptions, sensitive-looking generated artifacts, or ambiguous proprietary content.
- `warning`: low-risk but unnecessary public detail, stale internal references, overly specific implementation clues, or metadata that should be generalized.
- `info`: benign publication notes, such as no findings, intentionally public identifiers, or intentionally public attribution names in attribution contexts.

When in doubt, prefer `review-required` over `pass`.

## Workflow

1. Lock the audit scope and visibility context.
2. Inspect requested scope and collect candidate files/diffs:
   - staged diff for `staged-only`
   - working tree diff and untracked files for `pending-changes`
   - explicit files for `explicit-files`
   - tracked current tree for `current-tree`
3. For `public`, `public-intended`, `full-history`, or `full-repo`, inspect full reachable Git history, not just the current tree. Use commands such as:

   ```bash
   git rev-list --all
   git grep -n -I -i -e 'pattern' $(git rev-list --all) -- .
   git log --all --stat --oneline
   ```

   Avoid dumping large secrets into the conversation. Report file paths, commit ids, and redacted snippets only.
4. Inspect hosting/publication metadata when relevant:
   - repository description
   - homepage URL
   - topics
   - package metadata such as `package.json`, Python project metadata, crate metadata, or release notes
   - GitHub App / marketplace / README homepage text when the repo is used as an app or integration homepage
   - GitHub PR title/body when a PR exists
   - GitHub PR `.patch` and `.diff` views when a PR exists and the repo is public, public-intended, or visibility is unknown
5. Check for both secret-like patterns and privacy/context disclosure patterns.
6. Evaluate findings against red-list categories.
7. Assign severity:
   - `blocker`: unsafe for public commit/push
   - `review-required`: potentially risky, needs review before public push
   - `warning`: low-risk but should be cleaned up before publication when practical
   - `info`: low-risk note
8. If history is dirty, recommend one of:
   - rewrite history before first meaningful public use
   - rotate exposed credentials if any secret value was public
   - delete and recreate the public repo if the history is messy and the repo is brand new
   - leave history intact only when exposure is harmless and explicitly accepted
9. Produce concrete remediation guidance per finding.
10. Return a clear gate decision.

## Suggested pattern families

Use judgment and tune to the repository, but include at least these families for public-intended audits:

- Secret markers: `ghp_`, `github_pat_`, `BEGIN .*PRIVATE KEY`, `api[_-]?key`, `secret`, `password`, `token`, provider-specific key names.
- Local paths: `/home/`, `/Users/`, `C:\\Users\\`, `.openclaw`, `.ssh`, `.config/gh`, `.env`.
- Personal/context identifiers named by the user or visible in the task, such as private project names, internal runtime names, private repo names, machine names, workflow-specific aliases, local usernames, and private property/customer names. Treat public author/committer/coauthor names as context-sensitive: preserve them in attribution fields, but flag them when coupled to private operational context.
- Generated artifacts: `.log`, `.dump`, `.bak`, `.zip`, `.tar`, `.sqlite`, transcripts, screenshots, exported JSON, support bundles.
- Hosted PR artifacts: PR bodies, generated `.patch`/`.diff` files, closed PR refs, release notes, and issue comments when they contain copied task metadata.

Do not rely only on regex. Read surrounding context for ambiguous matches.

## Output format

Return a concise structured report:

```yaml
scope:
visibility_context:
gate_decision: # pass | review-required | block
history_checked: # true | false | not-applicable
metadata_checked: # true | false | not-applicable
blocker_findings:
warning_findings:
info_findings:
required_remediation:
safe_next_steps:
notes:
```

Output rules:
- If no issues in a category, return `[]`.
- Any `blocker` finding requires `gate_decision: block`.
- `review-required` is for non-blocking ambiguity, unnecessary personal/context disclosure, or policy-dependent cases.
- Keep remediation specific and immediately actionable.
- Do not quote full secrets or large private snippets. Redact aggressively.

## Gotchas

- Removing a secret in a later commit may not remove exposure from history.
- Rewriting branch history may not remove exposure from hosted PR artifacts; GitHub `refs/pull/*` refs are read-only and may require support purge, repo recreation, or temporary privacy containment when sensitive context appeared in a public PR.
- Repository descriptions, topics, release notes, package metadata, and homepages can leak context even when files are clean.
- Generated PR patches can leak context even when the current tree and PR body are clean.
- Test/demo files often carry real credentials by mistake.
- "Internal-only but harmless" assumptions are frequently wrong for public repos.
- A public trust homepage should explain the security model without naming private infrastructure unless that naming is intentionally public.
- Public-safety checks are separate from code correctness.

## Portability notes

- Keep checks hosting-provider agnostic (GitHub/GitLab/Bitbucket/public mirrors).
- For GitHub, `gh repo view` or the REST API can help inspect public metadata, but do not require GitHub-specific tooling if local metadata is enough.
- Use conservative defaults when repository visibility is uncertain.
- Prefer false-positive review over false-negative public exposure.
