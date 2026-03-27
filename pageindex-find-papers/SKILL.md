---
name: pageindex-find-papers
description: Find papers already present in a Page Index collection from bibliography references, citations, or free-form reference text. Use when the user provides one or more paper references in any format and wants the agent to search only the existing Page Index collection, verify exact matches carefully, report inaccessible or still-processing items as not found, and maintain or update a bibliography-to-Page-Index bridge mapping file for reuse.
---

# Pageindex Find Papers

## Overview

Find one or more papers already stored in a Page Index collection from bibliography-like input. Search only within the existing Page Index collection, verify matches carefully, and maintain a reusable bridge mapping between bibliography entries and Page Index filenames.

## Required Boundaries

- Use only Page Index MCP tools.
- Use only search, lookup, listing, metadata, and content-reading capabilities that query the existing Page Index collection.
- Never upload, ingest, process, or add papers to Page Index unless the user explicitly asks for that separate action.
- Never use internet search, OCR tools, or non-Page-Index retrieval methods to find the paper.
- Treat a paper that is still processing or otherwise inaccessible in Page Index as not found for the current task.
- If Page Index MCP tools are unavailable in the current runtime, stop and tell the user clearly.

## Inputs

Accept one or many bibliography references in any format, including messy or mixed formatting. For each requested paper, extract as much of the following as possible:

- title
- main author surname(s)
- publication year
- other distinguishing details when available

Process each paper independently, then summarize the batch.

## Bridge Mapping Memory

Before searching Page Index, check for an existing bridge mapping file first.

Preferred location:
- `memory/pageindex/`

Recommended file:
- `memory/pageindex/bibliography-to-pageindex-bridge.md`

Use this file to map bibliography content to one or more Page Index filenames.

Rules:
- If `memory/pageindex/` does not exist, do not infer a substitute path.
- Ask the user whether to create `memory/pageindex/` or whether another existing path should be used.
- If the mapping file exists, consult it before starting fresh Page Index searches.
- If a mapping exists, verify that the mapped Page Index file still exists and is accessible before trusting it.
- If a stored mapping is still valid, report that the paper was found through the existing bridge mapping and that the mapped file remains accessible.
- If a stored mapping is outdated, update it.
- If multiple Page Index files match the same bibliography entry, record all of them.
- Merge bibliography rows only when they are truly redundant and the match is exact in all major identifying fields.
- Do not collapse near-matches or uncertain duplicates.

## Search Workflow

### 1. Normalize the reference

For each requested paper:
- isolate the likely title
- isolate the main author surname or surnames
- isolate the publication year
- note any distinctive journal, conference, subtitle, or acronym clues

Do not over-trust formatting. Bibliography text may be noisy.

### 2. Check the bridge mapping first

If a bridge mapping file exists:
- look for an exact or highly confident match to the bibliography entry
- use the mapped Page Index filename as the first verification target
- verify that the mapped file is still present and accessible in Page Index

If the mapping succeeds and the file is accessible, consider the paper found and report that the mapping file resolved it.

### 3. Search Page Index using single-keyword passes

If no valid mapping resolves the paper, perform Page Index search passes using mostly single keywords.

Preferred search style:
- search title keywords one at a time
- search distinctive author surnames one at a time
- search the publication year when useful
- combine evidence across multiple searches rather than relying on one long query

Use multiple passes. Prefer precise single-keyword searches because Page Index search beam may behave better that way.

Reasonable pass order:
1. rare title keyword
2. second rare title keyword
3. first author surname
4. another author surname if available
5. publication year
6. alternate title keyword variants, abbreviations, acronyms, or subtitle fragments

If the first pass fails, continue with multiple keyword variations until the reasonable search space is exhausted.

### 4. Verify candidates carefully

When one or more candidates appear, verify them carefully before declaring success.

Check as many of the following as possible:
- exact or near-exact title match
- author match, especially first author and major listed authors
- publication year match
- journal, conference, or source match
- abstract, first page, or other visible content consistency
- filename consistency when informative

If multiple plausible matches exist, compare them explicitly and prefer the one with the strongest evidence.

If no candidate can be verified confidently, do not guess. Report the paper as ambiguous or not found, depending on the evidence.

### 5. Handle inaccessible or processing items

If a candidate exists in Page Index but is still processing, unavailable, or inaccessible:
- treat it as not found for the current task
- report the exact reason to the user
- do not count it as a successful match

### 6. Update the bridge mapping

After a verified result:
- add or update the bibliography-to-filename mapping
- include all verified matching filenames when there are multiple true matches
- update outdated filenames when the stored mapping no longer reflects the current collection

Keep the mapping reusable and conservative.

## Output Requirements

For each requested paper, report:
- the original bibliography entry or a short normalized version of it
- status: `found`, `found via bridge mapping`, `ambiguous`, or `not found`
- matched Page Index filename or filenames when found
- concise verification notes explaining why the match is correct
- exact failure reason when not found or inaccessible

When relevant, say explicitly:
- that the bridge mapping file was used first
- that the stored mapping was still valid
- that the stored mapping was outdated and was updated
- that a candidate existed but was still processing or inaccessible
- that all reasonable Page Index-only search passes were exhausted

## Non-Negotiable Rules

- Never search outside Page Index for this task.
- Never upload or process papers on your own initiative.
- Never treat a still-processing Page Index file as found.
- Never skip verification when multiple candidates exist.
- Never silently invent a bridge mapping location when `memory/pageindex/` is missing.
- Never over-compress distinct bibliography entries into one mapping unless the duplication is truly exact.
