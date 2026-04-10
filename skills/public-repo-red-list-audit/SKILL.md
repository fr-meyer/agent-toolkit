---
name: public-repo-red-list-audit
description: Use this skill when the user needs to check whether a repository, commit, staged diff, or file set contains content that should not be committed or pushed to a public repository. Apply it when requests involve secret exposure, private data leakage, internal-only material, or pre-push public-safety checks. Do not use it for generic code quality review or documentation-quality audits unless the core question is publish safety.
---

# Public Repo Red List Audit

## Goal

Prevent accidental publication of sensitive or non-public material by auditing repository content before commit or push to public remotes.

This skill is safety-focused and should be treated as a blocking gate when high-risk findings exist.

## Use this skill for

- pre-commit or pre-push checks for public repositories
- audits of staged/unstaged/untracked changes for public safety
- "is this repo safe to make public?" assessments
- identifying red-list content in files, diffs, logs, exports, configs, and docs

## Do not use this skill for

- generic code quality/style reviews
- documentation clarity audits
- architecture improvement recommendations unrelated to exposure risk
- resolving merge conflicts or Git workflow strategy

## Required inputs

Gather what is available:

- `repo_path`
- scope (`staged-only`, `pending-changes`, `explicit-files`, `full-repo`)
- remote visibility context (`public`, `private`, `unknown`, `public-intended`)
- optional policy overrides from user/org

If visibility is unknown and a push is requested, treat risk conservatively and run the audit.

## Red-list categories

Treat the following as high-priority risk classes:

1. Secrets and credentials
   - API keys, access tokens, passwords, private keys, signing keys, live connection secrets
2. Private or regulated data
   - real personal/customer data, financial/health/legal-sensitive records, production exports
3. Internal-only operational/security material
   - sensitive runbooks, internal architecture/network details, privileged procedures
4. Risky generated artifacts
   - logs, dumps, backups, support bundles that may contain tokens/data
5. Non-approved proprietary or internal business material
   - content not intentionally approved for public disclosure

## Workflow

1. Inspect requested scope and collect candidate files/diffs.
2. Evaluate findings against red-list categories.
3. Assign severity:
   - `blocker`: unsafe for public commit/push
   - `warning`: potentially risky, needs review before public push
   - `info`: low-risk note
4. Produce concrete remediation guidance per finding.
5. Return a clear gate decision.

## Output format

Return a concise structured report:

```yaml
scope:
visibility_context:
gate_decision: # pass | review-required | block
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
- `review-required` is for non-blocking ambiguity or policy-dependent cases.
- Keep remediation specific and immediately actionable.

## Gotchas

- Removing a secret in a later commit may not remove exposure from history.
- Test/demo files often carry real credentials by mistake.
- "Internal-only but harmless" assumptions are frequently wrong for public repos.
- Public-safety checks are separate from code correctness.

## Portability notes

- Keep checks hosting-provider agnostic (GitHub/GitLab/Bitbucket/public mirrors).
- Use conservative defaults when repository visibility is uncertain.
- Prefer false-positive review over false-negative public exposure.
