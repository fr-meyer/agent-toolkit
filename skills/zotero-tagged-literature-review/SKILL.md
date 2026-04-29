---
name: zotero-tagged-literature-review
description: Use this skill when the user wants to start from Zotero items selected by include/exclude tag rules, make sure those papers are available and verified in Page Index, read them, produce reusable per-paper review artifacts, synthesize one aggregate literature review, save it to a requested Markdown path, and retag the Zotero items based on success or failure. Apply it when requests combine Zotero queue tags, Page Index-backed paper reading, per-paper evidence extraction or summaries, and a final cross-paper literature review. Do not use it for pure literature-review drafting from already-prepared notes, pure Page Index finding or summarization, direct Zotero ingestion alone, or standalone tag maintenance.
---

# Zotero Tagged Literature Review

## Goal

Run an end-to-end workflow that starts from a **Zotero tag-defined paper set** and ends with:
- one saved aggregate literature review
- reusable per-paper review artifacts
- explicit Zotero outcome tagging

This skill owns the **orchestration layer**, not every specialized sub-step. Reuse the existing source-specific and synthesis-specific skills wherever they already fit.

## Best Fit

Use this skill when the user wants a workflow like:
- select Zotero papers by include/exclude tag rules
- ensure those papers exist in Page Index
- read the full papers from Page Index
- create per-paper evidence cards and optionally per-paper summaries
- synthesize a final multi-paper literature review
- save the review to a requested Markdown path
- retag the Zotero items after success/failure

Do not use this skill for:
- literature reviews that already start from prepared notes, summaries, or manually curated paper sets with no Zotero queue logic
- pure Zotero-to-Page-Index ingest workflows with no review deliverable
- pure Page Index paper resolution, reading, or summarization by itself
- generic tag cleanup or tag-management-only requests
- taxonomy classification workflows

## Scope-Splitting Decision

Keep this as **one orchestrator skill** because the user intent is one coherent job:

> take a Zotero-tagged batch of papers and turn it into one saved literature review with reusable review artifacts and final Zotero retagging

Do **not** fold this behavior into `literature-review`, `zotero-docai-ingest-to-pageindex`, or `pageindex-summarize-papers`, because those skills already have cleaner narrower ownership boundaries.

## Dependencies and Delegation

This skill should delegate specialized steps instead of re-implementing them.

Preferred reuse path:
- `zotero-docai-pipeline` - tag-based Zotero selection / export / tagging-capable batch discovery
- `zotero-docai-ingest-to-pageindex` - Zotero-backed Page Index ingest bridge when papers are not yet available in Page Index
- `pageindex-find-papers` - conservative duplicate checking and verification of the exact Page Index filenames that will be treated as source-of-record documents
- `pageindex-read-papers` - coverage-verified full-paper reading through Page Index
- `pageindex-summarize-papers` or `summarize-research-papers` - saved per-paper summary artifacts when the workflow needs reusable summaries, not just internal evidence cards
- `literature-review` - final cross-paper synthesis and review drafting

Treat the **verified Page Index paper** as the source of record for reading and synthesis once it is available.

## Required Inputs

Before running the full workflow, confirm or obtain:
- Zotero include-tag rule(s)
- Zotero exclude-tag rule(s)
- success tag
- error tag
- whether any staging / queue tag should be removed on success
- final literature review Markdown path
- whether per-paper summaries should be saved as files
- whether a partial final review is acceptable if some papers fail
- if support artifacts should be saved, the directory path for those artifacts

If the final review path is missing, ask for it instead of guessing.
If the user wants saved support artifacts but gives no artifact directory, ask for one instead of guessing.

## Output Artifacts

Main required deliverable:
- one aggregate literature review saved to the user-provided Markdown path

Default reusable intermediate artifact:
- one evidence card per fully read paper

Optional saved support artifacts:
- one per-paper summary report per paper when the user asked for saved summaries or the workflow materially benefits from them
- a saved manifest when the user asked for support artifacts

### Default artifact layout and naming

When the user requests saved support artifacts, prefer a stable subfolder layout under the chosen artifact directory:

- `evidence-cards/`
- `paper-summaries/`
- `cluster-syntheses/`
- `super-cluster-syntheses/`
- `manifests/`

Default filename guidance:
- evidence card: `<citation-key-or-short-title>--evidence-card.md`
- per-paper summary: `<citation-key-or-short-title>--summary.md`
- cluster synthesis: `cluster-<nn>--<short-theme-or-method-label>.md`
- super-cluster synthesis: `super-cluster-<nn>--<short-theme-or-domain-label>.md`
- manifest: `review-run-manifest.md`

Rules:
- prefer stable, human-readable filenames
- update an existing artifact in place when it is clearly the same paper or synthesis unit
- create a versioned copy only when the user explicitly wants versioning or when overwriting would destroy meaningful prior work
- keep naming consistent across all hierarchy levels so provenance stays easy to follow

For the detailed manifest shape, evidence-card content, saved-summary policy, paper-level success boundary, and partial-outcome reporting rules, read:
- `references/artifact-and-outcome-policy.md`

## Dynamic Scale-Aware Execution

This workflow must choose its synthesis strategy based on the size of the successfully readable paper set rather than always attempting one direct end-to-end synthesis in one live context.

### Default scale policy

After Zotero selection, Page Index verification, and paper-level read eligibility are known, determine the size of the synthesis-eligible set and choose the default route:

- 1-5 papers:
  - direct final synthesis is allowed
  - per-paper evidence cards are still required
  - saved per-paper summaries remain optional unless requested

- 6-20 papers:
  - process papers in small reading batches
  - save paper-level artifacts to files
  - perform final synthesis from saved artifacts rather than from a long accumulated live context

- 21-60 papers:
  - process papers in small reading batches
  - save paper-level artifacts
  - create intermediate cluster-level synthesis artifacts before producing the final review

- 61+ papers:
  - process papers in small reading batches
  - save paper-level artifacts
  - use multi-level hierarchical synthesis when needed:
    - paper-level artifacts
    - cluster-level syntheses
    - optional super-cluster syntheses
    - final aggregate review

These thresholds are defaults. If the environment, model context window, artifact verbosity, or paper complexity makes a smaller threshold safer, prefer the smaller threshold.

### Reading batch policy

For medium and large workflows, default reading batches should usually contain 3-5 papers.

Rules:
- finish one reading batch before moving to the next
- save durable artifacts before starting the next batch
- do not keep raw extracted paper content from earlier batches in active working context when file-backed artifacts already exist
- after each batch, prefer a clean context boundary before continuing if the conversation has become artifact-heavy

If the papers are unusually long, methodologically dense, or require rich evidence extraction, prefer the lower end of the batch range.

### Context reset and execution boundary policy

For medium and large workflows, do not assume the whole job should run in one uninterrupted live context.

Default execution guidance:
- 1-5 papers:
  - one live run is usually acceptable
- 6-20 papers:
  - prefer a clean context boundary between paper-reading and final synthesis
- 21-60 papers:
  - prefer isolated sub-runs for reading batches or cluster syntheses when available
  - prefer a fresh parent synthesis context for the final review
- 61+ papers:
  - default to file-backed handoffs between major stages
  - prefer isolated sub-runs for batch reading and intermediate syntheses when available

Rules:
- if durable artifacts have already been written, reload compact artifact outputs instead of carrying forward long in-chat state
- if context pressure is visible, stop expanding the current live context and switch to a fresh context boundary
- when unsure, prefer the smaller and cleaner execution boundary

### Direct-execution refinement mode

When the user wants a backlog drained quickly, wants active refinement rather than periodic maintenance, or explicitly rejects scheduler-driven execution, prefer a **direct live execution loop** over cron/watchdog-style orchestration.

Default behavior in this mode:
- use one direct long-lived parent worker or one actively managed small set of live workers rather than periodic scheduler wakeups
- re-read the live queue/manifest/review state immediately before every dispatch
- treat the queue's currently assigned lane batch as authoritative over any stale earlier plan
- after each verified durable completion, continue directly to the next smallest safe batch instead of waiting for a later scheduler cycle
- keep the concurrency cap explicit and small; more live workers are not a substitute for durable checkpoints
- when the user prioritizes speed, fill the safe concurrency cap deliberately rather than leaving lanes idle
- prefer **one live worker per active lane** as the default parallelism model for this workflow

Rules:
- do not use cron/watchdog as the primary driver when the user asked for rapid direct execution
- if live queue state advances while a plan is being prepared, abandon the stale plan and switch to the current authoritative batch
- if one paper in a batch blocks but others can land durably, salvage the largest truthful durable subset instead of replaying the whole batch unchanged
- if repeated non-durable attempts occur, change the execution unit or containment boundary rather than letting retry churn masquerade as progress
- keep scheduler-based recovery as an opt-in fallback only, not the default execution path for rapid refinement work
- when parallelism is increased, respect the verified lane/concurrency cap from the active queue policy rather than inventing extra workers outside the tracked lanes
- use available lanes promptly when they have an assigned active stage, but do not exceed **one active worker batch per lane** unless the workflow has been explicitly redesigned around stage-owned writer slots
- if the workflow is already lane-capped, improve throughput by shortening handoff time between durable completions and the next dispatch, not by oversubscribing more workers to the same lane

### Dynamic worker-budget policy

If the user wants to increase or decrease the number of live workers on the fly, do not treat the requested number as a direct instruction to duplicate normal writers on the same review track.

Default reusable rule:
- compute the safest worker mix from the current backlog shape each time the target changes
- fill **distinct durable-writer stage owners** first
- then fill any clearly safe **branch-scoped artifact-writer** opportunities
- only then use extra capacity for **read-only scout workers**

Definitions:
- a **durable writer** may write shared artifacts for exactly one stage owner
- an **artifact-writer** may write only branch-scoped durable artifacts such as per-paper summaries, evidence cards, and cluster syntheses for a non-overlapping paper set
- a **stage owner** is the pair of shared durable outputs that define the track, typically the aggregate review file plus the manifest file for that track
- a **scout** may help with source mapping, blocker screening, duplicate checks, and next-batch shaping, but must not write shared review/manifest/queue files

Rules:
- never run more than one durable writer against the same stage owner at the same time
- when the user changes the worker target, recompute the writer/scout mix before the next dispatch wave
- if additional safe distinct writer stages exist, use them before adding artifact-writers or scouts
- artifact-writers must never update the shared aggregate review, shared manifest, or shared queue state
- if no additional safe distinct writer stages or non-overlapping artifact-writing branches exist, extra workers must remain read-only scouts or remain unused
- if a single parent session hits its child-budget ceiling but safe distinct write domains still exist, switch to **multi-parent sharding** instead of duplicating writers on the same stage owner
- under multi-parent sharding, assign each shard parent a non-overlapping write domain and let that shard parent spawn only the children needed inside its owned domain
- if the workflow supports explicit runtime queue/control fields, expose the latest target, computed durable-writer slots, computed artifact-writer slots, computed scout slots, and recompute reason so the scaling decision stays auditable

For the detailed reusable dynamic worker-budget pattern, including a tiny operator-facing command convention such as `targetSubagents=<n>` and `targetSubagents=max-safe`, the requested-vs-effective capacity distinction, and the multi-parent sharding fallback, read:
- `references/dynamic-worker-policy.md`
- `references/multi-parent-sharding.md`

### Hierarchical synthesis policy

When the workflow uses hierarchical synthesis, do not treat the whole run as one ever-growing conversational draft.

Instead:
1. create paper-level evidence cards for every fully read paper
2. optionally create saved per-paper summaries when requested or clearly useful
3. group papers into bounded synthesis clusters
4. create one cluster-level synthesis artifact per cluster
5. if the cluster layer is still too large for a safe final synthesis, group cluster outputs into another higher-level synthesis layer
6. produce the final literature review from the highest stable synthesis layer plus any necessary spot-checking against lower-level artifacts

Use saved artifacts as the handoff boundary between levels. Do not rely on accumulated conversational memory as the primary storage layer for large workflows.

### Cluster formation policy

When cluster-level synthesis is required, build clusters using the most meaningful available grouping signal, in this order when possible:
1. user-requested grouping
2. explicit topic/theme similarity
3. method family
4. population/domain similarity
5. chronological grouping only when analytically justified
6. stable size-balanced fallback grouping if no stronger grouping is available

Examples of good clustering:
- method-family clusters:
  - self-supervised representation learning papers together
  - benchmark or evaluation papers together
  - clinical deployment or monitoring papers together
- domain or dataset clusters:
  - ICU monitoring papers together
  - wearable-device papers together
  - PPG benchmark dataset papers together
- topic/theme clusters:
  - signal quality estimation papers together
  - cuffless blood pressure estimation papers together
  - multimodal physiological fusion papers together

If no meaningful analytical grouping is available, use a stable size-balanced fallback:
- create roughly even clusters
- preserve a reproducible ordering rule
- avoid reshuffling papers arbitrarily between runs unless the evidence base changed

Do not create arbitrary clusters if a meaningful analytical grouping is available.

### Context budget discipline

For medium and large workflows:
- keep the active manifest compact
- keep only identifiers, filenames, statuses, and short evidence pointers in live context
- store long notes, evidence extracts, and summaries in files
- do not repeatedly restate previously saved artifact content in full
- do not treat earlier chat turns as the authoritative store of paper-level detail once artifacts have been written

If context pressure becomes visible, prefer writing and reloading compact artifacts over continuing to accumulate detailed in-chat state.

Allowed live-context content for medium and large workflows should usually be limited to:
- Zotero item identifiers
- verified Page Index filenames
- batch or cluster membership
- status flags
- short evidence pointers
- short synthesis claims that point back to saved artifacts

Do not paste long saved evidence cards, long paper summaries, or long cluster syntheses back into the main live context unless a specific ambiguity requires a targeted re-check.

## Required Workflow

### 1. Lock the workflow contract

Before running the batch:
- confirm the include/exclude tag logic
- confirm the intended success and error tags
- confirm whether the queue/staging tag should be removed on success
- confirm the final review path
- confirm whether per-paper summaries should be saved
- confirm the support-artifact directory if saved support artifacts are requested

If any of those are missing and cannot be inferred safely, ask only the minimum blocking question.

### 2. Select the Zotero working set conservatively

Use tag-based Zotero selection with explicit include/exclude logic.

Expected behavior:
- include tags define eligibility
- exclude tags define disqualification
- conflict resolution should be explicit

If the current Zotero-selection backend does **not** guarantee full pagination/exhaustion for large tag result sets, do **not** claim that the full matching Zotero queue was processed.

When completeness is uncertain because of pagination limits:
- report the limitation explicitly
- stop before claiming full queue coverage
- do not silently call the workflow complete

### 3. Build the item-to-paper manifest

For every selected Zotero item, build or update the working manifest.

The manifest should make the workflow traceable across Zotero selection, Page Index verification, reading, per-paper artifacts, final synthesis inclusion, and final tagging.

Read `references/artifact-and-outcome-policy.md` when you need the detailed field expectations.

### 4. Run a pre-dispatch blocker and reuse screen

Before dispatching any normal reading/summarization batch, screen the candidate papers for obvious blockers or obvious reusable wins.

Required checks:
- whether a verified full-paper summary or other durable paper artifact already exists on disk and is sufficient to advance the manifest honestly
- whether the local Zotero storage artifact directory or other required local source artifact is missing
- whether the environment is already known to lack a prerequisite needed for the next claimed action (for example writeback prerequisites)
- whether the same paper is already represented by a verified duplicate record that should be resolved first instead of reread
- whether the live queue/lane state still points at this exact batch, or whether a newer authoritative batch already superseded the planned dispatch

Rules:
- if a durable artifact already exists and is sufficient, reuse it immediately instead of dispatching a fresh normal worker
- if an obvious source-artifact blocker is already known, record the blocker explicitly at paper level before spending another retry on the same doomed path
- if a known environment limitation means a step cannot succeed, downgrade the planned action honestly instead of dispatching a worker that will only rediscover the same limit
- if duplicate resolution can settle the paper honestly, do that before launching a new reading batch
- if the live queue has already advanced to a newer authoritative batch, discard the stale plan and switch before dispatch

The goal is to prevent avoidable retries before they start.

### 5. Ensure Page Index availability

For each selected paper:
- check first whether it already exists in Page Index
- use `pageindex-find-papers` or an existing verified bridge mapping before attempting a fresh ingest
- only ingest papers that are still missing after that duplicate-checking step
- preserve canonical Zotero filenames whenever the ingest path supports that
- verify the actual resulting Page Index filename before treating the paper as ready

Do not silently accept degraded generic filenames such as `file.pdf` when the workflow depends on reliable mapping.
Do not skip the duplicate-check-first step just because a Zotero attachment URL is already available.

### 6. Resolve the verified Page Index source of record

Before reading or summarizing a paper:
- verify the exact Page Index filename that will act as the source of record
- store that mapping in the working manifest
- if multiple verified Page Index files exist, record all of them and identify which one is the primary reading target

### 7. Read the paper fully from Page Index

For each verified paper:
- use Page Index full-paper reading rules
- require explicit coverage verification before treating the paper as fully read
- if the paper is unresolved, inaccessible, or only partially read, do not treat it as fully eligible for high-confidence summary or synthesis

If the user still wants a partial workflow outcome after some papers fail:
- clearly separate successfully read papers from failed ones
- make the final synthesis scope explicit

### 7.25 Durable checkpoint pipeline

For refinement-style or queue-driven runs, prefer a **stepwise durable pipeline** over a single loose “complete the batch” instruction.

Default checkpoint order:
1. verify the exact source-of-record paper mapping for the current paper or batch
2. write or explicitly verify reuse of the per-paper summary artifact
3. update the manifest row(s)
4. update the aggregate review only after the relevant paper-level artifact and manifest state are durable
5. only then record queue/lane advancement or batch completion

Rules:
- do not collapse these checkpoints into one success claim unless the durable artifacts for the earlier checkpoints already exist on disk
- if the batch stalls after one or more checkpoints, record the truthful partial durable state rather than reverting to an all-or-nothing completion story
- if only reading or extraction happened but no downstream artifact checkpoint landed, stop the batch at that state and record `no_durable_progress`
- if a later checkpoint fails, preserve and report the earlier landed artifacts instead of hiding them behind a failed batch label
- prefer smaller checkpointed progress over broader but weakly verified “done” claims

### 7.35 Retry-exhaustion and reroute policy

When the same batch shape keeps failing file-backed verification, do not keep treating repeated retries as the default path.

Rules:
- after repeated `no_durable_progress` outcomes, narrow the batch boundary, split the mixed cluster, or reroute the lane to a smaller safer unit
- do not blindly re-dispatch an exhausted trio just because it was the last attempted batch
- if one paper appears to be the blocker, isolate that paper and let the salvageable remainder proceed separately when truthful
- if the cluster mixes materially different paper types (for example survey + benchmark + tooling/interface paper), prefer splitting earlier rather than forcing one shared completion boundary
- if a batch is paused because automatic retries were exhausted, the next step should usually be explicit reroute, explicit blocker recording, or smallest-safe subset salvage — not silent replay of the same unit

### 7.5 Enforce the false-success guard before claiming progress

A worker or sub-step must not report a meaningful completion unless at least one required durable artifact actually changed on disk.

For any paper-level or batch-level success claim, verify the claimed durable output first:
- manifest row changed appropriately
- review file changed appropriately when review inclusion is claimed
- per-paper summary file was written, updated, or explicitly verified as a reused durable artifact when summary progress is claimed
- Zotero writeback result file exists when writeback is claimed

Rules:
- if none of the required durable artifacts changed, return or record `no_durable_progress` rather than a success-like completion
- do not treat page fetches, partial reads, self-reported worker completions, or broad undifferentiated file dumps as success by themselves
- do not enqueue the same retry as if the prior attempt succeeded; record it explicitly as a non-durable attempt
- prefer failing small and honestly over inflating progress signals that the watchdog will later have to unwind
- after any `no_durable_progress` result, reassess the batch boundary itself before retrying; do not assume the same batch shape is still optimal
- if a batch can be partially salvaged with truthful durable outputs, record the landed subset first and isolate only the unresolved remainder for follow-up
- a completion report must identify the exact paper keys or synthesis units that advanced and the exact durable artifacts that changed; otherwise it is not enough to count as a verified batch success

Minimum completion report fields for any claimed durable batch outcome:
- `status`: `durable_progress`, `partial_durable_progress`, `no_durable_progress`, or `blocked`
- `advanced_item_keys`: exact paper keys that truly advanced, or an empty list
- `files_changed`: exact durable file paths changed on disk, or an empty list
- `count_delta`: exact before/after coverage numbers when review coverage moved, otherwise an explicit `no_change`
- `blocker`: exact blocker description when not all intended papers landed, otherwise `none`
- `writeback_claimed`: `true` only when a Zotero writeback result file exists on disk for the claimed items; otherwise `false`

### 8. Create per-paper evidence cards

For every paper that was fully read:
- create a compact evidence card
- keep it factual and synthesis-oriented
- make it easy to compare across papers later

Evidence cards are required even when saved per-paper summaries are also produced.

Read `references/artifact-and-outcome-policy.md` when you need the detailed evidence-card expectations.

### 9. Create per-paper summaries when useful

If the user requested reusable per-paper summary files, or if the workflow explicitly benefits from reusable summary artifacts:
- create one saved summary per paper
- keep the summary tied to the verified Page Index paper
- use `pageindex-summarize-papers` or `summarize-research-papers` for the actual saved-summary standard instead of improvising a new format here
- do not collapse multiple papers into one summary file

If the user did not ask for saved per-paper summaries:
- keep evidence cards as the minimum reusable intermediate layer
- do not force extra saved summary files by default unless the workflow explicitly calls for them

### 10. Choose the scale-aware synthesis route

Before generating the final review, choose the synthesis route that matches the number and complexity of successfully read papers.

Default policy:
- 1-5 papers: direct final synthesis is allowed
- 6-20 papers: synthesize from saved paper-level artifacts rather than from one long live context
- 21-60 papers: create cluster-level synthesis artifacts before the final review
- 61+ papers: add higher-level synthesis layers when needed before the final review

Do not keep escalating one flat conversation when the artifact set is already large enough to justify a file-backed handoff.

### 10.5 Handle failures at the correct hierarchy level

Failures should be contained at the smallest honest unit rather than collapsing the entire workflow by default.

Rules:
- if one paper fails inside a reading batch:
  - mark that paper as failed
  - continue the batch if the remaining papers are still usable
  - exclude the failed paper from downstream synthesis eligibility
- if one cluster-level synthesis fails:
  - do not pretend that cluster was synthesized successfully
  - continue with other completed clusters when the user allows partial outcomes
  - label the final review as partial if it excludes that failed cluster
- if one higher-level synthesis layer fails:
  - fall back to the highest completed lower layer when that still supports an honest partial result
  - otherwise stop and report the exact failed layer

Do not silently blur paper-level failures, cluster-level failures, and whole-run failures into one vague status.

### 11. Generate the aggregate literature review

Use the successfully read papers plus the highest stable artifact layer available to produce:
- one aggregate literature review

Possible synthesis bases include:
- evidence cards and verified full papers for small runs
- saved per-paper summaries when those were requested or clearly useful
- cluster-level synthesis artifacts for medium and large runs
- optional super-cluster synthesis artifacts for very large runs

The final review should:
- synthesize across papers rather than summarize them one by one
- stay grounded in the evidence cards and verified full papers
- reopen the full Page Index paper when a summary is too lossy or ambiguous
- state clearly if the synthesis excluded failed or unread papers
- state clearly when hierarchical synthesis layers were used instead of one flat direct drafting pass

Use `literature-review` for the actual synthesis-writing standard.

### 12. Save the final review

Write the final review to the user-provided Markdown path.

Rules:
- do not guess the final path
- use a stable, human-readable filename when the user gives a directory but leaves the final basename open
- if the user asked for only one final review file, do not split the review into multiple files without asking

### 13. Apply final Zotero tagging carefully

Use a paper-level success boundary rather than a vague whole-run success claim.

Default policy:
- for papers that met the success boundary: add the reviewed tag
- for papers that failed before reaching that boundary: add the error tag
- on failure: keep the queue / staging tag unless the user explicitly wants otherwise
- on success: remove the queue / staging tag only if the current environment can do that safely and explicitly

If the current environment cannot perform the requested remove-on-success behavior as a first-class supported action:
- report the limitation clearly
- do not pretend the workflow's retagging completed exactly as requested

Read `references/artifact-and-outcome-policy.md` when you need the exact success boundary and final reporting rules.

## Gotchas

- Do not treat per-paper summaries as more authoritative than verified full-paper access.
- Do not write a mini literature review for each paper.
- Do not skip the item-to-paper manifest; this workflow needs explicit traceability.
- Do not assume Zotero-item <-> Page Index mapping is obvious without recording it.
- Do not claim queue exhaustion when the upstream tag-selection system may still be paginated or truncated.
- Do not remove queue tags on failure by default.
- Do not silently accept degraded Page Index filenames when the workflow depends on stable mapping.
- Do not dispatch a normal worker when an obvious blocker or sufficient reusable durable artifact has already been identified.
- Do not keep executing a stale batch plan after the live queue has already advanced to a newer authoritative batch.
- Do not treat worker self-reports, page fetches, partial reads, or broad file dumps as success unless the required durable files actually changed on disk.
- Do not skip the durable checkpoint order just because a worker claims the whole batch is finished.
- Do not keep a mixed survey/benchmark/tooling batch together once early verification shows the papers do not share a clean durable completion boundary.
- Do not let retry churn stand in for progress; if repeated retries stay non-durable, change the batch boundary, split the mixed unit, or record the blocker.
- Do not interpret a higher user-requested worker count as permission to run multiple durable writers against the same review/manifest owner.
- Do not guess file paths for the final review or saved support artifacts.
- Do not keep raw paper details for dozens of papers in one growing live context once durable artifacts already exist.
- Do not fake a flat direct synthesis path when the workflow actually required cluster-level or multi-level aggregation.

## Evaluation Support

For trigger-boundary testing, read:
- `references/eval-prompts.json`

For reusable dynamic worker-budget design guidance, read:
- `references/dynamic-worker-policy.md`

## Portability Notes

- Keep the orchestration portable by delegating source-specific and synthesis-specific sub-steps.
- Do not hardcode Zotero library structure beyond the tag-selection and attachment concepts already required by the workflow.
- Treat current environment limitations explicitly; if an upstream tool cannot yet guarantee pagination completeness or requested retagging semantics, report that limitation instead of hiding it.
