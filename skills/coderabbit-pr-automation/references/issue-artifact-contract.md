# Issue Artifact Contract

## Purpose

This file defines the normalized input artifact expected by the `coderabbit-pr-automation` skill.

The artifact is the preferred runtime handoff between:
- deterministic extraction logic
- the remediation skill
- optional validation or adjudication steps

The goal is to give the skill a small, stable, machine-friendly representation of unresolved CodeRabbit review work, instead of raw GraphQL or provider-specific API payloads.

## Design goals

The artifact should be:

- normalized — remove irrelevant provider or API nesting
- bounded — include only the issue set needed for remediation
- portable — usable across agents and environments
- inspectable — easy for humans to read during debugging
- replayable — reusable for later dry-runs or debugging without re-fetching live API data

## Required top-level structure

A valid issue artifact must be a JSON object with these top-level keys:

- `pr`
- `issues`
- `metadata`

Optional top-level keys:
- `constraints`
- `context`
- `validation`

## `pr` object

`pr` describes the pull request under remediation.

Required fields:
- `number` — integer pull request number
- `title` — pull request title
- `branch` — head branch name
- `repository` — `owner/repo` identifier

Recommended fields:
- `url`
- `headSha`
- `baseBranch`

Example:

```json
"pr": {
  "number": 123,
  "title": "Fix auth edge cases",
  "branch": "feature/auth-fix",
  "repository": "example/repo",
  "url": "https://github.com/example/repo/pull/123",
  "headSha": "abc123def456",
  "baseBranch": "main"
}
```

## `issues` array

`issues` must be an array of unresolved actionable CodeRabbit issue entries.

The array may be empty. An empty array means no actionable work remains.

Each issue entry must include:

- `id`
- `threadId`
- `status`
- `file`
- `severity`
- `type`
- `title`
- `description`
- `agentPrompt`

Recommended:
- `commentId`
- `author`
- `line`
- `startLine`
- `endLine`
- `rawBody`

### Required issue rules

- `id` must be a stable issue identifier within the artifact
- `threadId` should be the upstream review-thread id when available
- `status` must be `"open"` in this strict schema
- `file` must be a repo-relative path
- `severity` must already be normalized
- `agentPrompt` must contain the operative bounded remediation instruction

Example minimal issue:

```json
{
  "id": "cr_001",
  "threadId": "PRRT_001",
  "status": "open",
  "file": "src/auth.ts",
  "severity": "high",
  "type": "bug",
  "title": "Authorization logic inverted",
  "description": "The current condition may allow unauthorized access on the failure path.",
  "agentPrompt": "Invert the authorization check and add a regression test for the unauthorized case."
}
```

## Severity normalization

Allowed values:

- `critical`
- `high`
- `medium`
- `low`
- `unknown`

Do not pass provider-native severity labels into the runtime artifact once normalization has happened.

## `agentPrompt` rules

`agentPrompt` is the most important content field.

It should contain the best available bounded remediation instruction for the issue.

Preferred source order:
1. extracted “Prompt for AI Agents” section from the upstream review
2. normalized fix instruction derived from the review comment
3. the issue description itself, if no better structure exists

Good `agentPrompt` qualities:
- concrete
- local to the issue
- free from irrelevant provider boilerplate
- actionable without requiring raw API payload inspection

## `constraints` object

Use `constraints` to communicate workflow limits.

Example:

```json
"constraints": {
  "maxCycles": 3,
  "allowCommit": false,
  "allowPush": false,
  "allowPrComment": false,
  "allowThreadResolution": false,
  "allowScopeExpansion": false
}
```

This section is optional but strongly recommended.

## `context` object

Use `context` to carry execution-target and preflight information for local remediation.

Recommended fields:
- `repoPath` — local repo path or working directory chosen by the caller
- `expectedRepository` — should match `pr.repository`
- `expectedBranch` — should match `pr.branch`
- `expectedHeadSha` — should match `pr.headSha` when available
- `workingTreeMustBeClean` — boolean preflight policy

Example:

```json
"context": {
  "repoPath": "/srv/repos/example-repo",
  "expectedRepository": "example/repo",
  "expectedBranch": "feature/auth-fix",
  "expectedHeadSha": "abc123def4567890",
  "workingTreeMustBeClean": true
}
```

The skill should not guess the impacted repo or branch when this context can be provided explicitly.

## `validation` object

If a previous validation pass is attached directly to the issue artifact, it may include rate-limit state for the current run.

Useful fields include:
- `rateLimited` — boolean
- `rateLimitScope` — string such as `reviewsPerHour`
- `retryAfterSeconds` — integer when known

## `metadata` object

Required fields:
- `artifactVersion`
- `createdAt`
- `source`

Example:

```json
"metadata": {
  "artifactVersion": "1",
  "createdAt": "2026-04-06T09:00:00Z",
  "source": "github-review-thread-normalizer"
}
```

## Validity rules

An artifact is valid enough for this skill when all of the following are true:

1. `pr` exists and contains:
   - `number`
   - `title`
   - `branch`
   - `repository`

2. `issues` exists and is an array.

3. Every issue entry contains:
   - `id`
   - `threadId`
   - `status`
   - `file`
   - `severity`
   - `type`
   - `title`
   - `description`
   - `agentPrompt`

4. Paths are repo-relative, not absolute host-specific paths.

5. The artifact does not require the skill to re-parse raw provider payloads to understand basic issue intent.

When `context` is present, the remediation environment should also be able to verify:
- the local repo path is the intended execution target
- the local repo identity matches `pr.repository`
- the local branch matches `pr.branch`
- the local HEAD matches the expected SHA when provided

## Malformed or incomplete artifacts

### Stop when:
- `issues` is not an array
- required `pr` fields are missing
- issue entries lack basic remediation content
- file paths are unusable or not repo-relative
- severity is not normalized
- the artifact appears to contain raw upstream payloads without normalization

### Proceed cautiously when:
- line numbers are missing but file and issue text are sufficient
- `rawBody` is absent but normalized fields are strong

## Anti-patterns

Do not use artifacts that:
- embed the full raw GraphQL response as the primary runtime payload
- include large unrelated thread history by default
- omit `agentPrompt`
- rely on provider-specific UI formatting to convey issue semantics
- use absolute host-specific paths as the main file locator
- widen scope from unresolved CodeRabbit findings into generic repo review
- leave repo or branch selection implicit when the caller can provide explicit execution context

## Summary

The issue artifact should be the smallest stable document that lets the skill answer:

- what PR is this?
- what unresolved CodeRabbit issues are actionable?
- where are they?
- how severe are they?
- what bounded remediation instruction should be followed?
- what workflow limits apply?
