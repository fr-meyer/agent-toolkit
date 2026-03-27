---
name: pageindex-find-papers
description: Find papers already present in a Page Index collection from bibliography references, citations, or free-form reference text. Use when the user provides one or more paper references in any format and wants the agent to search only the existing Page Index collection, verify matches carefully, treat still-processing or inaccessible Page Index items as not found, and maintain or update a bibliography-to-Page-Index bridge mapping file for later reuse.
---

# Pageindex Find Papers

## Overview

Find one or more papers already stored in a Page Index collection from bibliography-like input. Search only within the existing Page Index collection, verify matches conservatively, and maintain a reusable bridge mapping between bibliography entries and Page Index filenames.

## Hard Boundaries

- Use only Page Index MCP tools.
- Use only Page Index capabilities that inspect the existing collection, such as search, listing, lookup, metadata retrieval, and content reading.
- Do not use web search, OCR tools, local file search, or any non-Page-Index retrieval method for this task.
- Do not upload, ingest, process, or add papers to Page Index unless the user explicitly requests that as a separate action.
- Treat still-processing, unavailable, or inaccessible Page Index items as not found for the current task.
- If Page Index MCP tools are unavailable in the current runtime, stop and tell the user clearly.

## Accepted Inputs

Accept one or many references in any format, including:
- formal bibliography entries
- abbreviated citations
- messy copied references
- mixed-format batches

For each requested paper, extract as much of the following as possible:
- title
- main author surname or surnames
- publication year
- other distinguishing clues such as journal, conference, subtitle, acronym, or topic phrase

Process each requested paper independently, then summarize the batch.

## Bridge Mapping Memory

Check for an existing bridge mapping before doing fresh Page Index search work.

Preferred folder:
- `memory/pageindex/`

Recommended file:
- `memory/pageindex/bibliography-to-pageindex-bridge.md`

Use this file to map bibliography content to one or more Page Index filenames.

### Rules

- If `memory/pageindex/` does not exist, do not infer a substitute path.
- Ask the user whether to create `memory/pageindex/` or whether another existing path should be used.
- If the bridge mapping file exists, consult it first.
- If a mapping exists, verify that the mapped Page Index file still exists and is accessible before trusting it.
- If a stored mapping is still valid, report that the paper was resolved through the existing bridge mapping and that the mapped file remains accessible.
- If a stored mapping is outdated, update it.
- If multiple Page Index files truly match the same bibliography entry, record all of them.
- Merge bibliography rows only when they are truly redundant and match exactly on the major identifying fields.
- Do not merge near-matches or uncertain duplicates.

## Workflow

### 1. Normalize the reference

For each requested paper:
- isolate the likely title
- isolate the main author surname or surnames
- isolate the publication year
- note any distinctive journal, conference, subtitle, acronym, or uncommon title token

Do not over-trust input formatting. Bibliography text may be noisy, incomplete, or inconsistent.

### 2. Check the bridge mapping first

If a bridge mapping file exists:
- look for an exact or highly confident match to the bibliography entry
- use the mapped Page Index filename as the first verification target
- verify that the mapped file is still present and accessible in Page Index

If the mapping resolves the paper and the file is accessible, treat the paper as found and say that the mapping file resolved it.

### 3. Search Page Index with mostly single-keyword passes

If no valid mapping resolves the paper, search Page Index using mostly single-keyword passes.

Preferred search style:
- search one distinctive title keyword at a time
- search one author surname at a time
- search the year when useful
- combine evidence across passes instead of relying on one long query

Prefer single-keyword search because Page Index search beam may be more accurate that way.

Reasonable pass order:
1. rare title keyword
2. second rare title keyword
3. first author surname
4. another author surname if available
5. publication year
6. alternate title tokens, subtitle fragments, acronyms, or common variants

If the first pass fails, continue with additional reasonable keyword passes until the search space is exhausted.

### 4. Verify candidates conservatively

When one or more candidates appear, verify them before declaring success.

Check as many of the following as possible:
- exact or near-exact title match
- author match, especially first author and major listed authors
- publication year match
- journal, conference, or source match
- abstract, first page, or visible content consistency
- filename consistency when informative

If multiple plausible matches exist, compare them explicitly and prefer the candidate with the strongest evidence.

If no candidate can be verified confidently, do not guess. Report the result as ambiguous or not found, depending on the evidence.

### 5. Handle still-processing or inaccessible items

If a candidate exists in Page Index but is still processing, unavailable, or inaccessible:
- treat it as not found for the current task
- report the exact reason to the user
- do not count it as a successful match

### 6. Update the bridge mapping

After a verified result:
- add or update the bibliography-to-filename mapping
- include all verified filenames when there are multiple true matches
- update outdated filenames when the stored mapping no longer reflects the current Page Index collection

Keep the mapping conservative, reusable, and easy to audit later.

## Output Requirements

For each requested paper, report:
- the original bibliography entry or a short normalized version of it
- status: `found`, `found via bridge mapping`, `ambiguous`, or `not found`
- matched Page Index filename or filenames when found
- concise verification notes explaining why the match is correct
- exact failure reason when not found, still processing, or inaccessible

When relevant, say explicitly:
- that the bridge mapping file was checked first
- that the stored mapping was still valid
- that the stored mapping was outdated and was updated
- that a candidate existed but was still processing or inaccessible
- that all reasonable Page Index-only search passes were exhausted

## Non-Negotiable Rules

- Never search outside Page Index for this task.
- Never upload or process papers on your own initiative.
- Never treat a still-processing Page Index file as found.
- Never skip verification when multiple candidates exist.
- Never invent a bridge mapping location when `memory/pageindex/` is missing.
- Never collapse distinct bibliography entries into one mapping unless the duplication is exact on the major identifying fields.
