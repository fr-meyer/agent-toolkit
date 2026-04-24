---
name: literature-review
description: Use this skill when the user needs a narrative or thematic literature review, review outline, chapter draft, article-introduction review section, or cross-paper synthesis that turns multiple sources into themes, debates, methods, and research gaps. Apply it when requests involve framing a review question, setting review boundaries, organizing a search log or source matrix, synthesizing findings across papers, or drafting the review itself from papers, notes, or prior summaries. Do not use it for single-paper summaries, pure paper finding, taxonomy classification, meta-analysis calculations, or protocol-only systematic/scoping-review compliance work.
---

# Literature Review

## Goal

Help the agent plan, synthesize, and draft a **multi-source literature review** organized by themes, debates, methods, trends, or gaps rather than by one-paper-at-a-time summaries.

Default to **narrative / thematic literature reviews** and closely related deliverables such as:
- thesis or dissertation literature chapters
- article introduction literature sections
- gap memos grounded in multiple papers
- review outlines before prose drafting
- synthesis memos that compare a set of papers around a shared question

## Best Fit

Use this skill for:
- cross-paper synthesis
- turning papers, notes, or prior summaries into a review structure
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
- `pageindex-read-papers` or `nano-pdf` when paper content still needs to be read
- `pageindex-summarize-papers` or `summarize-research-papers` when per-paper summaries would materially improve the review workflow
- `zotero-docai-ingest-to-pageindex` or `pageindex-ingest-paper-urls` when the papers are not yet available in the working source system

Per-paper summaries are **optional support artifacts**, not a hard dependency. The real requirement is enough trustworthy source material to support cross-paper synthesis.

## Evidence Sufficiency Rules

Before producing a serious literature review, determine what the synthesis is actually based on.

Valid evidence bases can include:
- full papers
- substantial reading notes
- a source matrix built from actual reading
- already-written per-paper summaries
- a mixed evidence set that is clearly labeled

Rules:
- do not pretend abstracts alone are enough for a strong literature review unless the user explicitly wants a lightweight or preliminary review
- do not claim comprehensive field coverage unless the search and selection process actually supports that claim
- if the review is based partly or mainly on summaries or notes rather than direct paper reading, say so clearly
- if the evidence base is thin, downgrade the output honestly to an outline, preliminary synthesis memo, or scoped review plan

## Deliverable Modes

Choose the smallest deliverable that matches the user's request and the available evidence.

### 1. Scoped review plan
Use when the question or boundaries are still forming.

Return:
- working question
- proposed scope
- inclusion / exclusion boundaries
- initial theme candidates
- what evidence is still needed

### 2. Review outline
Use when the user wants structure before prose.

Return:
- title
- introduction role
- theme section headings
- key claims to develop under each heading
- likely gap / conclusion direction

### 3. Synthesis memo
Use when the user wants a compact cross-paper analysis rather than a polished chapter.

Return:
- main themes
- strongest agreements / disagreements
- method contrasts
- major gaps
- next-step questions

### 4. Full literature review draft
Use when the evidence base is strong enough and the user wants actual prose.

Return:
- introduction
- themed sections
- gap / controversy section
- conclusion
- reference placeholder or citation-ready notes

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
- whether the sources were read directly, summarized earlier, or supplied as notes
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

### 4. Draft with visible logic

Default section order for a full review:
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
- matches the evidence level actually available

## Template Use

Use `assets/literature-review-template.md` when the user wants any of the following:
- a fill-in review scaffold
- a structured outline before prose drafting
- a thesis/dissertation literature chapter skeleton
- a review section template for reuse
- a search log / source matrix / theme tracker scaffold

Template rules:
- adapt headings to the discipline and deliverable
- remove empty rows and prompts in the final output
- keep the template as a support scaffold, not as filler text
- if the user wants a shorter article-introduction review, compress the same logic into fewer sections rather than copying the full template mechanically

## Output / File Behavior

If the user wants the review saved to files:
- write to the path the user provided
- if no path was provided, ask for one instead of guessing
- keep one coherent review per file unless the user explicitly wants a split structure
- prefer stable, human-readable filenames

If the user did not ask for files:
- return the review, outline, or synthesis memo directly in the assistant response

## Systematic / Scoping Review Boundary

This skill can help with the **synthesis-writing side** of systematic or scoping reviews, but it is **not** the authority for:
- protocol design
- screening workflow control
- eligibility adjudication logs
- PRISMA compliance checking
- meta-analysis mechanics

If the user explicitly needs formal systematic/scoping-review reporting, keep the literature synthesis structure but label protocol, eligibility, screening, and PRISMA elements as additional requirements rather than pretending this skill alone covers them fully.

## Gotchas

- Do not write the review as one paper summary after another.
- Do not claim a comprehensive search unless the process record actually supports that claim.
- Do not invent inclusion/exclusion criteria after the fact without labeling them as proposed boundaries.
- Do not blur source evidence and your own interpretation.
- Do not let a literature review quietly degrade into a bibliography, abstract list, or taxonomy exercise.
- Do not overstate gaps just because only a small source set was available.
- Do not force chronology as the structure when themes or debates are the stronger organizing logic.
- Do not treat prior summaries as equivalent to direct reading without saying so.

## Output Expectations

Depending on the user's request, return one or more of:
- a scoped review plan
- a search log
- a source matrix
- an emerging-theme tracker
- a review outline
- a synthesis memo
- a drafted literature review section or chapter
- a concise list of major gaps, tensions, and next-step questions

When writing the actual review, make sure the final text reads as a coherent argument, not just as notes.

## Portability Notes

- Keep the workflow source-agnostic; use whatever paper-access workflow the environment already provides.
- Prefer Markdown unless the user explicitly asks for another format.
- Use relative references from the skill root.
- Do not assume Zotero, Page Index, or a specific citation manager unless the active task does.
