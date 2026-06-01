---
name: changeset-commit-partitioner
description: Use this skill when the user needs a mixed repository changeset partitioned into coherent commit groups with grounded commit messages. Apply it when requests involve splitting unrelated edits, grouping files by real commit intent, drafting Conventional Commits, preparing a multi-commit plan before sync, or identifying one thematic branch per feature before a PR workflow. Do not use it for merge conflict resolution, direct publish execution, PR creation, protected-branch enforcement, or destructive history rewriting.
---

# Changeset Commit Partitioner

## Goal

Convert a mixed local changeset into a truthful multi-commit plan with coherent commit groupings and grounded commit messages.

## Use this skill for

- splitting unrelated local changes before commit
- drafting commit groups by real change intent
- preparing Conventional Commit titles and bodies
- identifying ambiguous leftovers that should not be forced into a commit
- suggesting one thematic feature branch per coherent group when a repo policy requires branch-per-feature work

## Do not use this skill for

- merge conflict resolution
- rebasing strategy or branch recreation
- executing commits, pushes, or PR creation
- protected-branch enforcement
- force-push workflows
- rewriting already-published history

## Required inputs

Gather what is available:

- `repo_path`
- changed file list and diff context
- whether untracked files are allowed
- max commit count, if any
- whether execution or plan-only mode is desired
- whether the repo requires one branch per thematic feature
- target base branch, if branch suggestions are requested

## Default approach

1. Inspect the full changeset.
2. Group files by coherent commit intent.
3. Reject misleading or speculative groupings.
4. Draft a grounded commit title and body for each group.
5. When branch-per-feature policy applies, suggest a feature-branch name per group and treat each group as a possible PR unit.
6. Leave ambiguous remainder explicitly ungrouped.

## Coordination with publish and PR skills

Keep this skill as the planning layer.

- If the user asks to actually commit, sync, publish, or push after partitioning, use or hand off to `workspace-git-publish`.
- If the user asks to create, update, or prepare a GitHub PR, use or hand off to `github-pr-preflight`.
- If the repo policy says every thematic feature must start from the current upstream base, report branch suggestions such as `feat/<purpose>` but do not switch or recreate branches unless another skill/workflow is executing that step.
- If the current branch is `dev`, `main`, `master`, or another integration branch, highlight that committing there would violate a branch-per-feature policy and recommend starting a dedicated branch from the current upstream base.

## Grouping rules

Use:

- visible diff intent
- cross-file coherence
- whether one truthful short commit title can describe the group
- whether the group can land independently without hiding unrelated work

Do not hardcode repo-specific folder buckets as if they were universal.

## Output format

Return:

- commit groups
- file membership per group
- commit title and body draft per group
- suggested feature branch per group, when branch-per-feature policy applies
- ambiguous remainder
- reasons for any excluded files

## Validation

Before finishing, verify:

- each group has one honest commit purpose
- commit titles are grounded in visible evidence
- unrelated changes are not blended together
- leftovers are explicitly accounted for

## Gotchas

- "everything changed under one folder" is not a valid grouping rule by itself
- do not force leftover files into a dishonest commit
- smaller truthful commits are better than one blended commit
- a good multi-commit plan is about honesty, not just tidiness

## Portability notes

- use portable Git concepts and commit reasoning
- treat file paths as weak hints, not authoritative commit buckets
- keep planning separate from branch switching, push, PR, rebase, and scheduler concerns
