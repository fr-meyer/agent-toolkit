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

### 4. Ensure Page Index availability

For each selected paper:
- check first whether it already exists in Page Index
- use `pageindex-find-papers` or an existing verified bridge mapping before attempting a fresh ingest
- only ingest papers that are still missing after that duplicate-checking step
- preserve canonical Zotero filenames whenever the ingest path supports that
- verify the actual resulting Page Index filename before treating the paper as ready

Do not silently accept degraded generic filenames such as `file.pdf` when the workflow depends on reliable mapping.
Do not skip the duplicate-check-first step just because a Zotero attachment URL is already available.

### 5. Resolve the verified Page Index source of record

Before reading or summarizing a paper:
- verify the exact Page Index filename that will act as the source of record
- store that mapping in the working manifest
- if multiple verified Page Index files exist, record all of them and identify which one is the primary reading target

### 6. Read the paper fully from Page Index

For each verified paper:
- use Page Index full-paper reading rules
- require explicit coverage verification before treating the paper as fully read
- if the paper is unresolved, inaccessible, or only partially read, do not treat it as fully eligible for high-confidence summary or synthesis

If the user still wants a partial workflow outcome after some papers fail:
- clearly separate successfully read papers from failed ones
- make the final synthesis scope explicit

### 7. Create per-paper evidence cards

For every paper that was fully read:
- create a compact evidence card
- keep it factual and synthesis-oriented
- make it easy to compare across papers later

Evidence cards are required even when saved per-paper summaries are also produced.

Read `references/artifact-and-outcome-policy.md` when you need the detailed evidence-card expectations.

### 8. Create per-paper summaries when useful

If the user requested reusable per-paper summary files, or if the workflow explicitly benefits from reusable summary artifacts:
- create one saved summary per paper
- keep the summary tied to the verified Page Index paper
- use `pageindex-summarize-papers` or `summarize-research-papers` for the actual saved-summary standard instead of improvising a new format here
- do not collapse multiple papers into one summary file

If the user did not ask for saved per-paper summaries:
- keep evidence cards as the minimum reusable intermediate layer
- do not force extra saved summary files by default unless the workflow explicitly calls for them

### 9. Choose the scale-aware synthesis route

Before generating the final review, choose the synthesis route that matches the number and complexity of successfully read papers.

Default policy:
- 1-5 papers: direct final synthesis is allowed
- 6-20 papers: synthesize from saved paper-level artifacts rather than from one long live context
- 21-60 papers: create cluster-level synthesis artifacts before the final review
- 61+ papers: add higher-level synthesis layers when needed before the final review

Do not keep escalating one flat conversation when the artifact set is already large enough to justify a file-backed handoff.

### 9.5 Handle failures at the correct hierarchy level

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

### 10. Generate the aggregate literature review

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

### 11. Save the final review

Write the final review to the user-provided Markdown path.

Rules:
- do not guess the final path
- use a stable, human-readable filename when the user gives a directory but leaves the final basename open
- if the user asked for only one final review file, do not split the review into multiple files without asking

### 12. Apply final Zotero tagging carefully

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
- Do not guess file paths for the final review or saved support artifacts.
- Do not keep raw paper details for dozens of papers in one growing live context once durable artifacts already exist.
- Do not fake a flat direct synthesis path when the workflow actually required cluster-level or multi-level aggregation.

## Evaluation Support

For trigger-boundary testing, read:
- `references/eval-prompts.json`

## Portability Notes

- Keep the orchestration portable by delegating source-specific and synthesis-specific sub-steps.
- Do not hardcode Zotero library structure beyond the tag-selection and attachment concepts already required by the workflow.
- Treat current environment limitations explicitly; if an upstream tool cannot yet guarantee pagination completeness or requested retagging semantics, report that limitation instead of hiding it.
