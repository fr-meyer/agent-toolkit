---
name: changeset-commit-partitioner
description: Use this skill when the user needs a mixed repository changeset partitioned into coherent commit groups with grounded commit messages. Apply it when requests involve splitting unrelated edits, grouping files by real commit intent, drafting Conventional Commits, or preparing a multi-commit plan before sync. Do not use it for merge conflict resolution, branch strategy decisions, or destructive history rewriting.
---

# Changeset Commit Partitioner

## Goal

Convert a mixed local changeset into a truthful multi-commit plan with coherent commit groupings and grounded commit messages.

## Use this skill for

- splitting unrelated local changes before commit
- drafting commit groups by real change intent
- preparing Conventional Commit titles and bodies
- identifying ambiguous leftovers that should not be forced into a commit

## Do not use this skill for

- merge conflict resolution
- rebasing strategy
- force-push workflows
- rewriting already-published history

## Required inputs

Gather what is available:

- `repo_path`
- changed file list and diff context
- whether untracked files are allowed
- max commit count, if any
- whether execution or plan-only mode is desired

## Default approach

1. Inspect the full changeset.
2. Group files by coherent commit intent.
3. Reject misleading or speculative groupings.
4. Draft a grounded commit title and body for each group.
5. Leave ambiguous remainder explicitly ungrouped.

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
- keep planning separate from push/rebase/scheduler concerns
