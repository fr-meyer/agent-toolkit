---
name: coderabbit-pr-automation
description: Use this skill when the user wants to automate, inspect, or operate a bounded workflow for unresolved CodeRabbit PR review threads, especially when requests involve triaging CodeRabbit issues, consuming a normalized review-issue artifact, planning or applying targeted fixes, interpreting validation output, deciding whether a second remediation pass is warranted, or summarizing a remediation run. Do not use it for generic GitHub Actions setup, generic code review, raw GraphQL extraction as the primary task, or unrelated repository automation.
---

# CodeRabbit PR Automation

## Goal

Help the agent run a safe, bounded remediation workflow for unresolved CodeRabbit PR review threads.

This skill is for the reasoning and remediation layer of the workflow. It works best when a deterministic extraction step has already produced a normalized issue artifact.

## Default approach

- Prefer a normalized issue artifact over raw provider payloads.
- Treat the normalized artifact as the source of truth for actionable unresolved CodeRabbit issues.
- Keep work tightly bounded to the extracted issue set.
- Use at most 3 total remediation cycles unless the user explicitly requests a different policy.
- Continue looping only while validation remains available and not rate-limited.
- Default to conservative behavior:
  - no commit
  - no push
  - no PR comment posting
  - no thread resolution
  - no branch switching
  - no broad scope expansion

## Scope boundaries

Use this skill for:
- triaging unresolved CodeRabbit review issues
- interpreting a normalized CodeRabbit issue artifact
- planning or applying bounded fixes for those issues
- interpreting validation results after a remediation pass
- deciding whether another bounded pass is justified
- summarizing a remediation run

Do not use this skill for:
- generic GitHub Actions setup or CI authoring
- generic code review unrelated to CodeRabbit
- raw GraphQL extraction as the primary task
- broad repo cleanup or opportunistic refactoring
- repository administration such as branch management, secret setup, or runner installation
- automatic commit, push, or thread resolution in the default workflow

## Preferred inputs

The preferred primary input is a normalized issue artifact that includes:
- PR metadata
- unresolved actionable CodeRabbit issue entries
- file and line context when available
- normalized severity and issue type
- issue descriptions
- extracted or normalized fix prompts
- optional workflow constraints

Optional supporting inputs:
- repo path or working directory selected by the caller
- expected repository, branch, and head SHA for preflight verification
- validation results from a previous pass
- repo-local diff summary
- preflight result
- list of allowed files
- current cycle count or previous run summary

If the user asks for runtime remediation but only raw provider output exists, prefer normalizing the issue data first.

## Preferred execution context

When the workflow operates on a local clone, the caller should provide or enforce:
- the local repo path or working directory to use
- the expected repository identity matching `pr.repository`
- the expected branch matching `pr.branch`
- the expected head SHA matching `pr.headSha` when available
- the working-tree cleanliness policy for the run

Do not guess the repo or branch from ambient machine state when the caller can specify them explicitly.

## Workflow

1. Confirm the request is in scope.
2. Verify repo execution context and preflight assumptions when a local clone is involved.
3. Inspect the issue artifact and determine whether actionable work exists.
4. Prioritize issues and define a bounded remediation plan.
5. Apply or guide a targeted remediation pass.
6. Review validation output if available.
7. Decide whether another pass is justified.
8. Summarize the outcome and stop within policy limits.

## Procedure

### 1. Confirm scope and mode

Determine which of these modes applies:

- design mode — refine the workflow, policy, or boundaries
- triage mode — inspect issues and determine actionability
- remediation mode — plan or apply bounded fixes
- adjudication mode — interpret validation output and decide next step
- summary mode — summarize what happened in a run

If the request is mainly about CI wiring, runner setup, or unrelated PR review, this skill is not the right fit.

### 2. Verify repo execution context

When a local repository is in play, verify the execution target before remediation:

- confirm the working directory is inside a Git repository
- confirm the local repository matches `pr.repository`
- confirm the current branch matches `pr.branch`
- confirm `HEAD` matches the expected SHA when provided
- confirm the working-tree cleanliness policy is satisfied

If this preflight fails, stop immediately.

Do not guess the impacted repo or branch.

### 3. Inspect the issue artifact

Read the normalized artifact first.

At minimum, inspect:
- PR identity
- issue count
- issue severity ordering
- file paths and line context
- issue titles and descriptions
- fix prompts or `agentPrompt`
- workflow constraints, if provided

If the artifact is malformed, incomplete, or ambiguous enough to prevent bounded remediation, stop and say what is missing.

### 4. Determine whether work is actionable

Treat an issue as actionable when:
- it is unresolved
- it is part of the normalized CodeRabbit issue set
- it contains enough context to support a bounded fix
- it does not obviously require broad redesign by default

If the issue set is empty or clearly non-actionable, stop and summarize that there is no remediation work to perform.

### 5. Plan a bounded remediation pass

Prioritize:
1. critical and security issues
2. high-severity correctness issues
3. clear warning-level issues still inside scope
4. lower-priority items only when they remain tightly local

Planning rules:
- prefer minimal, issue-local changes
- prefer coherence over scattered micro-edits when several issues affect the same local code path
- include tests only when directly justified
- do not widen into unrelated cleanup

### 6. Apply or guide remediation

Use the normalized issue description and fix prompt as the operative specification.

Rules:
- stay inside the extracted issue scope
- avoid unrelated refactors
- avoid changing repository state beyond the requested remediation
- keep the workflow conservative unless the user explicitly asks for more aggressive automation

When several issues overlap in the same code path, it is acceptable to make one coherent local change that resolves them together.

### 7. Interpret validation output

When validation output is available:
- inspect remaining criticals and warnings first
- distinguish unresolved original issues from newly introduced issues
- identify whether remaining findings are:
  - clearly actionable and still inside scope
  - low-priority nits
  - ambiguous
  - evidence that the workflow should stop rather than continue

If the validator reports a review quota, hourly limit, or rate-limit condition:
- stop further validation attempts in the current run
- skip any remaining loop that depends on fresh validation
- summarize that validation was skipped because of rate limiting

### 8. Decide whether another pass is justified

Default maximum: 3 total remediation cycles.

Another pass is justified when:
- meaningful critical, high, or medium findings remain
- they are still inside the original scope
- the next remediation step is reasonably clear

Do not continue when:
- only low-priority nits remain
- the remaining work would require broad redesign
- the output is too ambiguous
- validation is rate-limited or otherwise unavailable for loop continuation
- the cycle limit has already been reached

### 9. Summarize the result

Return a concise summary including:
- PR identity
- number of actionable issues inspected
- what was fixed, proposed, or deferred
- whether validation passed cleanly
- whether another pass was used
- what remains unresolved
- whether the workflow stopped due to scope or policy limits

## Stop conditions

Stop immediately when:
- no actionable issues remain
- the issue artifact is missing or malformed
- repo, branch, or expected head SHA preflight does not match
- the required remediation context is too ambiguous
- the work would require broad repo-wide changes not justified by the extracted issue set
- the cycle limit is reached
- only nits remain
- validation is rate-limited for the current run
- validation output is insufficient to justify another pass

## Gotchas

- Do not treat raw GraphQL output as the ideal runtime input when a normalized issue artifact is expected.
- Do not let the workflow drift from bounded remediation into generic review or cleanup.
- Do not guess which local clone or branch should be modified; require explicit repo context and verify it.
- A useful fix prompt is not permission for repo-wide refactoring.
- Another pass is a bounded retry, not an endless polish loop.
- CodeRabbit CLI rate limiting is a hard stop for validation-dependent looping in the current run.
- Keep deterministic extraction logic outside the skill when possible.

## Resources

Read only when needed:
- `references/issue-artifact-contract.md` — use when validating or interpreting the issue artifact
- `references/github-action-integration.md` — use when integrating this skill with GitHub Actions or a similar orchestration layer
- `references/pipeline-stages-and-stop-rules.md` — use when deciding whether to continue, stop, or authorize another pass
- `references/actionable-issues.sample.json` — use as a fixture example for the expected issue artifact shape
- `references/validation-result.sample.json` — use as a fixture example for the expected validation artifact shape
- `references/eval-prompts.json` — use when testing trigger quality against should-trigger and should-not-trigger prompts

Run only when needed:
- `scripts/validate-issue-artifact.py` — use to verify artifact structure before remediation
- `scripts/summarize-validation-result.py` — use to reduce validation output into a simpler adjudication summary

## Portability notes

- Prefer artifact-driven input over runtime dependence on raw provider APIs.
- Keep orchestration and environment setup outside the skill where possible.
- Avoid host-specific paths and product-specific assumptions in the main workflow.
- Treat CodeRabbit as the review source, but keep the remediation flow portable across agent runtimes.
