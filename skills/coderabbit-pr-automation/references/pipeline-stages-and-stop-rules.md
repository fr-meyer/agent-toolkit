# Pipeline Stages and Stop Rules

## Purpose

This file defines the default execution stages, safety boundaries, and stop conditions for the `coderabbit-pr-automation` workflow.

Use this reference when:
- designing or refining the remediation pipeline
- deciding how a run should progress from issue intake to completion
- deciding whether another remediation pass is justified
- determining when the workflow should stop early

## Core principle

The pipeline should behave like a careful remediation workflow, not a generic autonomous repo-maintenance agent.

That means:
- narrow scope
- explicit inputs
- conservative defaults
- bounded retries
- early exit when no useful work remains

## Default workflow shape

```text
1. Intake
2. Execution-target preflight
3. Artifact inspection
4. Actionability decision
5. Remediation planning
6. Remediation pass
7. Validation review
8. Another-pass decision
9. Summary and stop
```

## Stage 1: Intake

### Goal
Confirm that the request and inputs are appropriate for this workflow.

### Early exit conditions
Stop if:
- the request is not actually about CodeRabbit remediation
- the user is asking for generic CI, generic repo cleanup, or unrelated PR review
- the required issue artifact is missing and remediation is impossible without it

## Stage 2: Execution-target preflight

### Goal
Confirm that the local repo, branch, and optional head SHA match the intended execution target.

### Minimum checks
- working directory is inside a Git repository
- local repo identity matches `pr.repository` when available
- current branch matches `pr.branch`
- current HEAD matches the expected SHA when provided
- working-tree cleanliness policy is satisfied

### Early exit conditions
Stop if:
- the local clone does not match the intended repository
- the current branch does not match the intended branch
- the current HEAD does not match the expected SHA when provided
- the working tree violates the run policy

Do not guess the impacted local repo or branch.

## Stage 3: Artifact inspection

### Goal
Inspect the normalized issue artifact and confirm it is usable.

### Minimum checks
- `pr` exists
- `issues` exists and is an array
- each issue has enough content to support bounded remediation
- file paths are repo-relative and usable
- the artifact is already normalized enough that raw provider payload parsing is not required

### Early exit conditions
Stop if:
- the artifact is malformed
- the issue entries do not contain enough information to reason about fixes
- the artifact is mostly raw provider output without normalization
- file paths are missing or unusable

## Stage 4: Actionability decision

### Goal
Decide whether there is meaningful remediation work to do.

### An issue is actionable when
- it is unresolved
- it belongs to the normalized CodeRabbit issue set
- it contains enough context for a bounded fix
- it does not obviously require broad redesign by default

### Default priority ordering
1. critical and security issues
2. high-severity correctness issues
3. medium-severity issues clearly inside scope
4. low-priority items only if still tightly local

### Early exit conditions
Stop if:
- `issues` is empty
- all remaining issues are non-actionable
- only informational or clearly non-remediable items remain

## Stage 5: Remediation planning

### Goal
Create a bounded plan for the next remediation pass.

### Planning rules
- prefer minimal local changes
- prefer coherence when several issues affect the same code path
- include tests only when directly justified
- avoid opportunistic cleanup
- avoid architecture-wide changes unless the user explicitly asks for them

## Stage 6: Remediation pass

### Goal
Apply or guide targeted fixes for the selected issue set.

### Conservative defaults
Unless explicitly overridden:
- no commit
- no push
- no PR comment posting
- no thread resolution
- no branch switching
- no broad scope expansion

### Allowed by default
- one coherent local change that resolves multiple nearby issues
- test updates directly required by the fix
- touching a small related file when necessary to complete the bounded remediation

### Not allowed by default
- dependency upgrades
- unrelated cleanup
- style-only repo churn
- broad refactors
- speculative fixes outside the extracted issue set

## Stage 7: Validation review

### Goal
Interpret validation output and decide what remains.

### Preferred validation questions
- Are any critical, high, or medium findings still present?
- Are the remaining findings part of the original issue set?
- Were new issues introduced by the remediation pass?
- Are the remaining findings local and actionable?

### Early exit conditions
Stop if:
- validation is clean enough
- only low-priority nits remain
- validation reports a rate limit or quota condition for the current run
- validation output is too ambiguous to justify another pass
- continuing would require scope expansion beyond the workflow’s default policy

## Stage 8: Another-pass decision

### Default cycle limit
Maximum 3 total remediation cycles.

### Another pass is justified when
- critical, high, or medium findings remain
- the remaining issues are still inside the original workflow scope
- the next action is reasonably clear
- the workflow has not yet reached its cycle limit

### Another pass is not justified when
- only nits remain
- remaining issues are broad redesign requests
- findings are too ambiguous
- validation is rate-limited or otherwise unavailable for loop continuation
- the next pass would require widening beyond the original bounded issue set
- the workflow has already reached the cycle limit

## Stage 9: Summary and stop

### A good summary should include
- PR identity
- number of actionable issues inspected
- what was fixed, proposed, or deferred
- whether validation passed cleanly
- whether another pass was used
- what remains unresolved
- why the workflow stopped

## Stop rules

Stop immediately when:
- the request is out of scope
- execution-target preflight fails
- the issue artifact is missing or malformed
- the issue set is empty
- no actionable issues remain
- the required remediation context is too ambiguous
- the work would require broad repo-wide changes not justified by the extracted issue set
- the cycle limit has been reached
- validation is rate-limited for the current run
- validation output is insufficient to justify further action
- only low-priority nits remain

## Scope-expansion rules

### Scope expansion is not allowed by default

The workflow should not widen into:
- generic code review
- cleanup unrelated to extracted issues
- style harmonization
- dependency updates
- architectural modernization

### Limited local expansion may be acceptable when
- a directly related test file must be updated
- a closely coupled helper function must change to complete the same local fix
- two extracted issues clearly share one local root cause

This is local completion, not general widening.

## Practical decision table

### Case: no issues
- Decision: stop
- Reason: no actionable work

### Case: artifact malformed
- Decision: stop
- Reason: cannot safely reason about the issue set

### Case: one or more high-severity local issues, clear fix path
- Decision: remediate
- Reason: bounded remediation is appropriate

### Case: validation shows only nits after first pass
- Decision: stop
- Reason: another pass is not justified

### Case: validation shows one remaining high- or medium-severity issue inside scope
- Decision: another pass allowed
- Reason: meaningful work remains and is still bounded

### Case: validator reports hourly review quota or rate limit
- Decision: stop
- Reason: validation-dependent looping must stop for the current run

### Case: validation shows broad redesign concerns
- Decision: stop
- Reason: outside bounded default workflow
