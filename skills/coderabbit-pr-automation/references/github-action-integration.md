# GitHub Action Integration

## Purpose

This file describes how to integrate the `coderabbit-pr-automation` skill into a GitHub Actions-based workflow.

This integration pattern is recommended, not mandatory. The skill itself should remain usable outside GitHub Actions when a compatible issue artifact is available.

The GitHub Action should act as the orchestration and plumbing layer, while the skill acts as the reasoning and bounded remediation layer.

## Core principle

Do not ask GitHub Action YAML to perform open-ended reasoning.

Use the GitHub Action to:
- wake the workflow
- run deterministic extraction and normalization steps
- invoke the agent runtime with the normalized artifact
- upload outputs and logs

Use the skill to:
- interpret the issue artifact
- decide whether the issue set is actionable
- plan and execute bounded remediation
- interpret validation output
- decide whether another pass is warranted
- summarize the run

## Recommended workflow shape

```text
GitHub event or manual dispatch
  -> self-hosted or suitable runner wakes
  -> fetch raw review-thread data
  -> normalize into actionable issue artifact
  -> invoke agent runtime with artifact path
  -> coderabbit-pr-automation skill activates
  -> skill performs triage, remediation, and adjudication
  -> workflow uploads logs and artifacts
  -> stop
```

## Recommended trigger strategy

### First rollout
Prefer:
- `workflow_dispatch`

Why:
- easier debugging
- explicit operator control
- fewer surprise runs
- simpler artifact inspection

### Later rollout
After manual runs are stable, consider:
- pull request review events
- review comment events
- other provider-specific review update events

Keep `workflow_dispatch` even after automation is enabled.

## Runner guidance

Prefer running this workflow on:
- a self-hosted runner
- or another runner with the full repo and tooling environment already available

The remediation workflow often depends on:
- repository-local context
- authenticated GitHub CLI access
- code-editing agent availability
- validation tooling availability

The workflow should choose the local clone explicitly rather than letting the skill infer it from ambient machine state.

## Responsibility split

### GitHub Action responsibilities
The Action should own:
- wake-up and scheduling
- environment setup
- deterministic scripts
- artifact persistence
- runtime invocation
- artifact upload
- timeout and fail-fast policy

### Helper script responsibilities
Scripts should own:
- raw API fetch
- normalization
- schema validation
- optional validation-result reduction

### Skill responsibilities
The skill should own:
- issue interpretation
- bounded remediation planning
- workflow guardrails
- validation adjudication
- second-pass decisions
- run summary generation

## Input contract for the Action

Before invoking the agent runtime, the workflow should ideally produce:
1. a normalized issue artifact such as `actionable-issues.json`
2. optional supporting outputs such as:
   - repo path or working directory for the intended local clone
   - expected repository identity, branch, and head SHA for preflight
   - preflight result
   - current diff summary
   - validation output from a previous pass

The Action should pass the artifact location into the runtime in a way that makes the path explicit and stable.

## Invocation pattern

The exact invocation depends on the agent runtime in use.

The integration pattern should follow this structure:

1. produce the issue artifact at a known path
2. invoke the runtime with a bounded prompt
3. explicitly reference the artifact path
4. make the task narrow enough that the skill triggers naturally

Example prompt shape:

```text
Use the CodeRabbit PR automation workflow on the normalized issue artifact at:
automation/coderabbit/out/actionable-issues.json

Keep the work bounded to the extracted unresolved CodeRabbit issue set.
Do not commit, push, post PR comments, or resolve threads.
If validation output exists, use it to decide whether another pass is justified.
```

## Recommended workflow phases

### Phase 1: deterministic extraction
Run scripts to:
- identify the target PR
- fetch unresolved review-thread data
- normalize actionable CodeRabbit issues

### Phase 2: artifact validation
Before invoking the skill:
- confirm the issue artifact exists
- confirm the artifact is structurally valid
- optionally stop early if issue count is zero

### Phase 2.5: execution-target preflight
Before invoking remediation on a local clone:
- confirm the working directory is inside a Git repo
- confirm the local repo matches `pr.repository`
- confirm the current branch matches `pr.branch`
- confirm `HEAD` matches the expected SHA when provided
- confirm working-tree cleanliness policy is satisfied

Stop early if any of these checks fail.

### Phase 3: agent invocation
Invoke the agent runtime with:
- artifact path
- bounded remediation instruction
- workflow limits

### Phase 4: optional validation
If the workflow includes a validator such as CodeRabbit CLI:
- store the validation output
- optionally feed the normalized validation result back into another agent pass
- if the validator reports a rate limit or quota condition, stop the loop immediately and skip further validation in the current run

### Phase 5: artifact upload
Upload:
- normalized issue artifact
- raw extraction output if helpful
- validation output
- summary text
- diff summaries or logs

## Early-exit policy

The Action should stop early when:
- the target PR cannot be determined
- no unresolved actionable CodeRabbit issues exist
- artifact creation fails
- the issue artifact is malformed
- required tooling is unavailable
- execution-target preflight fails

Do not invoke the skill for obvious no-op runs.

## Safe defaults for v1

Recommended defaults:
- no commit
- no push
- no PR comment posting
- no thread resolution
- no branch switching
- max 3 remediation cycles
- no unbounded scope expansion
- stop looping immediately when validation is rate-limited

These should be enforced either:
- in the issue artifact `constraints`
- in the invocation prompt
- or both

## What not to put in the Action YAML

Do not put these directly into YAML unless they are trivially deterministic:
- complex issue triage logic
- fuzzy severity interpretation
- remediation strategy reasoning
- provider-specific prompt interpretation
- broad file-selection heuristics

If the YAML starts to act like a reviewer or coding assistant, too much logic is in the wrong layer.

## Logging and artifacts

The Action should capture enough output to debug the run later.

Recommended artifacts:
- raw issue-fetch output
- normalized issue artifact
- validation output
- agent logs when available
- summary text
- diff summary or patch output when appropriate

When validation is skipped because of rate limiting, record that reason explicitly in the summary or artifacts.

## Portability note

GitHub Actions is one good orchestration layer, not a requirement of the skill itself.

The skill should remain usable in other environments so long as they can provide:
- a normalized issue artifact
- a suitable code-editing runtime
- optional validation outputs

## Summary

The clean integration model is:

- GitHub Action = trigger and plumbing
- scripts = deterministic transformations
- skill = bounded reasoning and remediation policy
