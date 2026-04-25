# Artifact and Outcome Policy

Read this file when the workflow needs more detail about:
- what the working manifest should capture
- what belongs in a per-paper evidence card
- when saved per-paper summaries are worth creating
- how to decide success vs failure at the paper level
- how to report partial final-review outcomes honestly

## Working Manifest

For each selected paper, keep a structured working record with at least:
- Zotero item key
- Zotero attachment key when available
- paper title
- citation key when available
- original selection tags relevant to the workflow
- canonical Zotero filename
- verified Page Index filename or filenames
- read / summary / synthesis eligibility status
- paper-level artifact paths when saved
- cluster assignment when hierarchical synthesis is used
- cluster-level or higher-level synthesis inclusion status when applicable
- final tagging outcome

This manifest does not need to become a saved file by default.
- If the user requested saved support artifacts, write it into the chosen artifact directory.
- Otherwise it may remain an internal working artifact used to keep the workflow traceable.

For medium and large workflows:
- keep the live manifest compact
- use short pointers to saved artifacts instead of pasting full artifact contents into working context
- treat saved files, not prior chat turns, as the durable handoff boundary between workflow stages

## Evidence Cards

Evidence cards are the factual spine of this workflow.

A good evidence card should contain:
- citation / short label
- research question or task
- domain / dataset / setting
- method or study type
- main findings
- limitations
- likely synthesis themes
- notable evidence anchors when practical

## Quality Standard

The highest-quality default stack for this skill is:
1. full-paper reading
2. structured evidence extraction
3. per-paper summary artifact
4. final cross-paper synthesis

For larger workflows, expand that stack into a hierarchical chain when needed:
1. full-paper reading
2. structured evidence extraction
3. paper-level evidence cards
4. optional per-paper summaries
5. cluster-level synthesis artifacts
6. optional higher-level synthesis artifacts
7. final cross-paper synthesis

Rules:
- evidence cards are required process artifacts
- per-paper summaries are strongly recommended saved artifacts, not the primary authority
- the final literature review should be grounded first in the evidence cards and verified full-paper access, not only in prose summaries
- if needed during synthesis, reopen the verified full paper in Page Index instead of treating the per-paper summary as the final authority
- do not create a "literature review" for each individual paper; per-paper artifacts should be evidence cards and summaries, not mini multi-source reviews

## Per-Paper Summaries

If the user requested reusable per-paper summary files, or if the workflow explicitly benefits from reusable summary artifacts:
- create one saved summary per paper
- keep the summary tied to the verified Page Index paper
- use `pageindex-summarize-papers` or `summarize-research-papers` for the actual saved-summary standard instead of improvising a new format here
- do not collapse multiple papers into one summary file

If the user did not ask for saved per-paper summaries:
- keep evidence cards as the minimum reusable intermediate layer
- do not force extra saved summary files by default unless the workflow explicitly calls for them

## Cluster-Level and Higher-Level Syntheses

When the paper set is too large for a safe flat synthesis pass:
- create bounded cluster-level synthesis artifacts from saved paper-level artifacts
- if cluster outputs are still too large for a safe final synthesis, create another bounded aggregation layer
- keep every aggregation layer explicitly traceable back to the contributing paper-level artifacts
- prefer analytically meaningful clustering over arbitrary chunking when a meaningful grouping signal is available

Cluster-level and higher-level synthesis artifacts are intermediate review supports, not replacements for paper-level provenance.

## Paper-Level Success Boundary

Define success at the paper level as:
- the paper was verified in Page Index
- the paper was fully read
- its evidence card was produced
- it was actually included in the final saved review's evidence base

Default policy:
- for papers that met that success boundary: add the reviewed tag
- for papers that failed before reaching that boundary: add the error tag
- on failure: keep the queue / staging tag unless the user explicitly wants otherwise
- on success: remove the queue / staging tag only if the current environment can do that safely and explicitly

If the current environment cannot perform the requested remove-on-success behavior as a first-class supported action:
- report the limitation clearly
- do not pretend the workflow's retagging completed exactly as requested

## Failure and Partial-Success Rules

A failed paper should not automatically void the whole workflow, but it must be handled honestly.

If some papers fail:
- add the failure tag to those papers when supported
- keep the queue / staging tag by default
- exclude those papers from the "fully read" evidence base
- label the final literature review as partial if it was produced from only the successful subset
- report the omitted items explicitly

Do not overclaim that the final literature review covers all matched Zotero items unless it truly does.

## Final Reporting

Always report:
- how many Zotero items were selected
- how many were confidently mapped to Page Index papers
- how many were fully read
- how many per-paper evidence cards were produced
- how many per-paper summary files were written, if any
- how many cluster-level or higher-level synthesis artifacts were produced, if any
- where the final review was saved
- which items were tagged as success vs error
- whether any requested queue-tag removal could not be completed exactly as requested
- whether pagination or mapping limitations weakened completeness claims

When hierarchical synthesis was used, also report:
- the synthesis layers that were used
- the grouping basis used for cluster formation when that materially affects interpretation
- whether the final review was produced from paper-level artifacts directly or from higher-level aggregation artifacts
