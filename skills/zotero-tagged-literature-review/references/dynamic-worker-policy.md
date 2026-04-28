# Dynamic Worker Policy

Use this reference when the user wants the literature-review refinement workflow to scale the live worker count up or down during the run.

## Goal

Let the user change the requested subagent count dynamically while keeping shared durable artifacts safe.

## Core model

Separate workers into three classes:

1. **Durable writers**
   - may write per-paper summaries, manifest rows, aggregate review files, and queue/runtime state
   - each durable writer must own exactly one **stage owner** at a time

2. **Artifact-writers**
   - may write only branch-scoped durable artifacts such as per-paper summaries, evidence cards, and cluster syntheses
   - artifact-writers must own a non-overlapping paper set or branch scope
   - artifact-writers must not modify the shared aggregate review, shared manifest, or shared queue state

3. **Scouts**
   - read-only helpers used for source mapping, duplicate checks, blocker screening, and next-batch shaping
   - scouts must not write shared review, manifest, or queue artifacts

A **stage owner** is the shared durable output boundary for one track, usually:
- one aggregate review file
- one manifest file

Default stage-owner key:
- `<reviewPath>::<manifestPath>`

## Safe scaling rule

When the user requests a worker count `N`:

1. identify all currently runnable distinct stage owners
2. allocate durable writers to distinct stage owners first
3. cap durable writers at **one per stage owner**
4. if `N` is larger than the number of safe distinct stage owners, allocate the remainder to non-overlapping artifact-writers only when clearly bounded branch-scoped writing work exists
5. after writer slots are safely filled, allocate any further remainder to scouts only if read-only support work is genuinely useful
6. if no useful artifact-writing or scout work exists, leave the extra capacity unused rather than creating unsafe duplicate writers

## Recompute triggers

Recompute the writer/scout allocation whenever:
- the user changes the target worker count
- a worker completes
- a stage blocks or pauses
- a new stage becomes runnable
- heavy-stage guardrails change

## Tiny operator-facing command convention

When the workflow exposes runtime control, prefer a tiny text convention that is easy to type and easy to parse.

Recommended commands:
- `targetSubagents=<n>`
  - set the requested live worker budget directly
  - the value is a **request**, not an unconditional granted count
  - example: `targetSubagents=2`
  - example: `targetSubagents=4`
  - example: `targetSubagents=6`
  - example: `targetSubagents=12`
- `targetSubagents=max-safe`
  - use the highest currently safe worker count based on distinct stage owners and guardrails
- `targetSubagents=min-safe`
  - reduce to the smallest still-useful worker count, usually one durable writer unless the workflow is blocked
- `scouts=auto|off`
  - `auto`: allow extra read-only scout workers when writer slots are already filled safely
  - `off`: disable scouts and keep all extra capacity unused

Interpretation rules:
- changing `targetSubagents` must trigger immediate recomputation before the next dispatch wave
- `max-safe` must not bypass the one-writer-per-stage-owner rule
- there should be **no fixed global min/max in the policy itself** unless an external platform/runtime limit is actually known
- if the requested value is higher than the current safe durable-writer count, allocate the remainder to artifact-writers first when safe branch-scoped writing work exists, then to scouts only when useful; otherwise leave it unused
- if the runtime queue is writable, mirror the effective result into explicit control fields such as `requestedTargetSubagents`, `effectiveSafeSubagentsNow`, `unfilledRequestedCapacity`, `computedDurableWriterSlots`, `computedArtifactWriterSlots`, `computedScoutSlots`, and `recomputeReason`

## Minimum explicit control fields

If the runtime queue or orchestrator state is writable, prefer exposing at least:
- `requestedTargetSubagents`
- `effectiveSafeSubagentsNow`
- `unfilledRequestedCapacity`
- `computedDurableWriterSlots`
- `computedArtifactWriterSlots`
- `computedScoutSlots`
- `distinctRunnableWriterStages`
- `activeWriterStageIds`
- `activeScoutStageIds`
- `recomputeReason`
- `lastRecomputedAt`

These fields are not required by the skill format itself, but they make dynamic scaling decisions auditable and easier to debug.

## Heavy-stage guardrails

If some stages are materially heavier or riskier than others, define explicit guardrails such as:
- default preferred max number of concurrent heavy durable writers
- which heavy stages should not normally run together
- when a user-requested higher-throughput mode may override the default preference

## Default recommendation

Prefer this order:
1. safe distinct durable writers
2. non-overlapping artifact-writers
3. read-only scouts
4. unused surplus capacity

That order is safer than forcing the requested worker count through duplicate writers on the same track.

## Runtime child-cap fallback: multi-parent sharding

If one parent session hits a runtime child limit before the workflow reaches its safe writer/artifact-writer capacity, do not respond by duplicating writers on the same stage owner.

Instead:
1. re-read the authoritative queue or orchestrator state
2. identify the remaining safe distinct write domains
3. open multiple **shard parents**, each with a non-overlapping owned domain
4. let each shard parent spawn only the children needed for its owned domain
5. keep ownership explicit so two shard parents never write the same shared durable target

Default shard-parent ownership model:
- one shard parent may own one or more full **stage owners** for shared-file durable writing
- one shard parent may also own branch-scoped artifact-writing work inside its domain
- a shard parent must not dispatch work outside its assigned domain

Default domain keys:
- shared-file durable domain: `<reviewPath>::<manifestPath>`
- branch-scoped artifact domain: `<reviewPath>::<manifestPath>::<branch-or-paper-scope>`

Use multi-parent sharding when:
- a real per-session child-budget ceiling is the throughput bottleneck
- multiple safe distinct stage owners or branch scopes still exist
- the workflow can assign non-overlapping write ownership cleanly

Do not use multi-parent sharding when:
- the remaining work all targets the same shared review/manifest pair
- the branch scopes are not cleanly separated on disk
- the throughput bottleneck is missing source material rather than child-budget pressure

## Gotchas

- Do not confuse more workers with more safe writers.
- Do not let artifact-writers touch shared review, manifest, or queue artifacts.
- Do not let scouts modify shared durable artifacts.
- Do not leave scaling decisions implicit when the user is actively changing worker targets.
- Do not keep a fixed worker cap if the workflow can safely expose more distinct stage owners.
- Do not raise concurrency without rechecking whether the current backlog shape actually supports it.
- Do not treat `targetSubagents=<n>` as permission to duplicate durable writers on the same stage owner.
