---
name: literature-review
description: Use this skill when the user needs a narrative or thematic literature review, literature-review section, chapter draft, or cross-paper synthesis that turns multiple sources into themes, debates, methods, and research gaps. Apply it when requests involve scoping a review question, organizing a search log or source matrix, synthesizing papers across themes, or drafting the review itself, even if the user does not explicitly say "literature review." Do not use it for single-paper summaries, pure paper finding, taxonomy classification, or protocol-only systematic/scoping-review compliance work.
---

# Literature Review

## Goal

Help the agent plan, synthesize, and draft a **multi-source literature review** that is organized by themes, debates, methods, or gaps rather than by one-paper-at-a-time summaries.

Default to **narrative / thematic literature reviews** and closely related deliverables such as:
- thesis or dissertation literature chapters
- article introduction literature sections
- gap memos grounded in multiple papers
- structured review outlines before drafting

## Best Fit

Use this skill for:
- cross-paper synthesis
- turning a pile of papers or notes into a review structure
- making search / inclusion boundaries explicit before drafting
- identifying recurring themes, tensions, and gaps across papers
- drafting or revising a literature review section using a reusable template

Do not use this skill for:
- single-paper summaries
- paper discovery by itself
- source-specific retrieval workflows
- taxonomy classification
- strict PRISMA/protocol compliance as the main task
- meta-analysis calculations

## Dependencies and Delegation

This skill owns the **review synthesis and drafting workflow**, not every upstream source-access step.

When the task depends on finding or preparing papers first, delegate to the relevant existing skill before drafting:
- `pageindex-find-papers` for Page Index paper resolution
- `pageindex-read-papers` or `nano-pdf` when full paper content still needs to be read
- `pageindex-summarize-papers` or `summarize-research-papers` when the user first needs per-paper summaries
- `zotero-docai-ingest-to-pageindex` or `pageindex-ingest-paper-urls` when the papers are not yet available in the working source system

Do not pretend a literature review is complete when the underlying papers were never actually accessed.

## Default Workflow

### 1. Lock the review frame before drafting

Before writing the review, determine or explicitly propose:
- working title
- central research question or problem
- purpose of the review
- key concepts / variables
- disciplinary lens or theory, if relevant
- timeframe
- population / geography / domain context
- inclusion criteria
- exclusion criteria
- expected citation style
- final deliverable form

If some of these are missing, ask only for the minimum details needed to avoid a fake review boundary. If the user prefers, propose a draft scope and mark it clearly as provisional.

### 2. Build or normalize the evidence base

For each source set, keep track of:
- what sources were actually available
- what search or selection path was used, if the user wants process transparency
- what kind of evidence each source contributes
- what is still missing

If the user wants a review with process transparency, maintain:
- a search record
- a source matrix
- an emerging-theme tracker

Use the template asset when that structure helps:
- `assets/literature-review-template.md`

### 3. Synthesize across sources, not one source at a time

Organize the body around:
- themes
- debates
- methodological differences
- chronological shifts only when they matter analytically
- unresolved gaps

For each theme section:
1. make a claim about the literature
2. compare multiple sources
3. evaluate evidence strength, context, and limitations
4. surface tensions, disagreement, or blind spots
5. connect the section to the larger review logic

### 4. Draft the review with visible logic

Default section order:
1. introduction
2. themed sections
3. gap / controversy / unresolved problem
4. conclusion
5. references placeholder or citation-ready notes

When the user wants an outline first, provide the outline before drafting full prose.

When the user wants prose, write in synthesis-first form:
- claim -> comparison -> evaluation -> gap / transition

### 5. Finish with a quality pass

Before finalizing, verify that the draft:
- answers the stated review question
- uses themes rather than source-by-source summary as the main structure
- synthesizes multiple sources per major section
- evaluates evidence quality or limits where relevant
- names disagreement, contradiction, or uncertainty
- ends with a clear gap or take-away
- does not overclaim search coverage or comprehensiveness

## Template Use

Use `assets/literature-review-template.md` when the user wants any of the following:
- a fill-in review scaffold
- a structured outline before prose drafting
- a thesis/dissertation literature chapter skeleton
- a review section template for reuse

Template rules:
- adapt headings to the discipline and deliverable
- remove empty rows and prompts in the final output
- keep the template as a support scaffold, not as filler text
- if the user wants a shorter article-introduction review, compress the same logic into fewer sections rather than copying the full template mechanically

## Systematic / Scoping Review Boundary

This skill can help with the **synthesis-writing side** of systematic or scoping reviews, but it is **not** the authority for protocol-only work, screening compliance, PRISMA compliance, or meta-analysis mechanics.

If the user explicitly needs formal systematic/scoping-review reporting, keep the literature synthesis structure but clearly label any protocol, eligibility, screening, and PRISMA elements as additional requirements rather than pretending this skill alone covers them fully.

## Gotchas

- Do not write the review as one paper summary after another.
- Do not claim a comprehensive search unless the process record actually supports that claim.
- Do not invent inclusion/exclusion criteria after the fact without labeling them as proposed boundaries.
- Do not blur source evidence and your own interpretation.
- Do not let a literature review quietly degrade into a bibliography, abstract list, or taxonomy exercise.
- Do not overstate gaps just because only a small source set was available.
- Do not force chronology as the structure when themes or debates are the stronger organizing logic.

## Output Expectations

Depending on the user's request, return one or more of:
- a scoped review plan
- a search log
- a source matrix
- an emerging-theme tracker
- a review outline
- a drafted literature review section or chapter
- a concise list of major gaps, tensions, and next-step questions

When writing the actual review, make sure the final text is readable as a coherent argument, not just as notes.

## Portability Notes

- Keep the workflow source-agnostic; use whatever paper-access workflow the environment already provides.
- Prefer Markdown unless the user explicitly asks for another format.
- Use relative references from the skill root.
- Do not assume Zotero, Page Index, or a specific citation manager unless the active task does.
