# Multi-Parent Sharding

Use this reference when a single parent session's child budget becomes the main bottleneck but the literature-review backlog still contains safe non-overlapping write domains.

## Goal

Push concurrency beyond a single parent session's child ceiling **without** allowing shared-file write collisions.

## Core idea

Split orchestration into multiple **shard parents**.

Each shard parent owns a disjoint write domain and may spawn children only inside that domain.

Default ownership rule:
- one shared-file durable writer per stage owner
- one shard parent per owned shared-file stage owner set
- artifact-writers may run inside a shard only for non-overlapping branch scopes

## Default write-domain model

Use these ownership keys:

1. shared-file durable domain
   - key: `<reviewPath>::<manifestPath>`
   - only one durable writer may own this key at a time across the entire workflow

2. branch-scoped artifact domain
   - key: `<reviewPath>::<manifestPath>::<branch-or-paper-scope>`
   - only one artifact-writer may own this key at a time across the entire workflow

## When to switch from single-parent dispatch

Switch when all of these are true:
- the current parent session has hit or is about to hit a real child-budget ceiling
- safe distinct stage owners or branch-scoped artifact domains still remain
- each proposed shard can be assigned a clean non-overlapping ownership boundary

Do not switch just because the user requested a large number. The bottleneck must be real and the domains must be safe.

## Default shard-parent workflow

1. Re-read the authoritative queue immediately before dispatch.
2. Compute the safe domain graph:
   - durable stage-owner domains
   - branch-scoped artifact domains
   - optional read-only scout domains
3. Partition the graph into non-overlapping shard-parent domains.
4. Spawn one shard parent per partition that is actually useful now.
5. Give each shard parent a strict ownership contract:
   - what it may write
   - what it must not write
   - how to verify durable progress on disk
6. Let each shard parent spawn its own children only inside its owned domain.
7. Reconcile only from disk-backed artifacts, not from child self-reports alone.

## Recommended shard-parent contract

Each shard parent should be told explicitly:
- owned stage owner(s)
- owned branch scope(s), if any
- whether it may launch durable writers, artifact-writers, scouts, or some combination
- the exact forbidden shared targets outside its domain
- the required disk-backed success criteria
- the requirement to re-read the live queue before each child dispatch

## Child role split inside a shard

Preferred order inside each shard:
1. one shared-file durable writer for each owned stage owner that is actually runnable
2. non-overlapping artifact-writers for branch-scoped durable artifacts
3. read-only scouts only when they still help

## Verification standard

Do not count these as durable progress by themselves:
- PageIndex reads
- source mapping
- self-reported completion
- broad status dumps

Count only on-disk durable artifacts such as:
- updated shared review files
- updated shared manifests
- new or updated per-paper summaries
- new or updated evidence cards
- new or updated cluster syntheses

## Gotchas

- Never assign two shard parents the same shared-file durable domain.
- Never let two artifact-writers own the same branch-scoped artifact domain.
- Do not let a shard parent silently expand beyond its declared domain.
- Re-read the live queue before dispatch; a stale partition is not authoritative.
- If repeated no-durable-progress occurs inside one shard, narrow or split that shard instead of replaying it unchanged.
