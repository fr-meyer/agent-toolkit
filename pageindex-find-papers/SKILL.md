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

## Required Preflight

Before doing fresh Page Index search work, check the bridge mapping location first.

Preferred folder:
- `memory/pageindex/`

Recommended file:
- `memory/pageindex/bibliography-to-pageindex-bridge.md`

Rules:
- If `memory/pageindex/` does not exist, do not infer a substitute path.
- Ask the user whether to create `memory/pageindex/` or whether another existing path should be used.
- This strict first-run pause is intentional. Do not start fresh Page Index searching until that location question is resolved.
- If the bridge mapping file exists, consult it first.

## Bridge Mapping Rules

Use the bridge mapping file to map bibliography content to one or more verified Page Index filenames.

Major identifying fields means, at minimum:
- normalized title
- first author surname
- publication year

Use additional evidence such as second author, source, subtitle, acronym, or visible content when needed to resolve ambiguity.

Rules:
- The bridge mapping file must contain only successfully found and verified papers.
- Do not store not-found papers in the bridge mapping file.
- Do not store ambiguous candidates in the bridge mapping file.
- Do not store inaccessible or still-processing files in the bridge mapping file.
- If a mapping exists, verify that each mapped Page Index file still exists and is accessible before trusting it.
- Even when a mapped file exists and is accessible, do a light re-verification against the major identifying fields before treating it as valid.
- If a stored mapping is incomplete, contradictory, low-confidence, or malformed, do not treat it as authoritative. Use it only as a search lead, then verify normally.
- If a stored mapping is still valid, report that the paper was resolved through the existing bridge mapping and that the mapped file remains accessible.
- If a stored mapping is outdated, update it.
- If multiple Page Index files truly match the same bibliography entry, record all verified files.
- For multiple verified files, distinguish between duplicate library copies, alternate versions, and uncertain relation in the notes.
- Merge bibliography rows only when they match exactly on the major identifying fields.
- Do not merge near-matches or uncertain duplicates.
- If an old mapped filename no longer exists or is no longer accessible, do not silently keep it as valid.

### Recommended mapping entry shape

Use a compact, auditable Markdown structure such as:

```md
## <normalized short label>
- Bibliography: <original bibliography text>
- Normalized title: <title or best title guess>
- Authors: <main surnames>
- Year: <year>
- Page Index filenames:
  - <filename 1>
  - <filename 2>
- Match type:
  - duplicate library copy | alternate version | mixed verified set
- Last verified: <YYYY-MM-DD>
- Notes: <why this mapping is trusted or why multiple verified files are grouped>
```

Keep the original bibliography text whenever possible so future searches can reuse it directly.

## Batch Handling

When the user provides multiple references in one request:
- preserve the user-visible order in the final output
- process each reference independently
- if two request rows are exact duplicates on the major identifying fields, you may reuse the same verified search result
- if two rows are only similar, keep them separate unless the duplication is exact on the major identifying fields
- if one verified search result resolves multiple truly identical references, say so explicitly in the output

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
- lightly re-verify the mapped file against title, first author surname, and year before treating it as resolved

If the mapping resolves the paper and the file is accessible, treat the paper as found and say that the mapping file resolved it.

### 3. Search Page Index with mostly single-keyword passes

If no valid mapping resolves the paper, search Page Index using mostly single-keyword passes.

Preferred search style:
- search one distinctive title keyword at a time
- search one author surname at a time
- search the year when useful
- combine evidence across passes instead of relying on one long query

Prefer single-keyword search because Page Index search beam may be more accurate that way.

Minimum required search passes before concluding not found, unless the input is too sparse to support them:
1. one rare or highly distinctive title keyword
2. a second title keyword or subtitle fragment
3. first author surname
4. publication year
5. one alternate token such as acronym, uncommon token, variant spelling, or another author surname when available

Reasonable additional passes:
- another author surname
- another uncommon title token
- acronym expansion or abbreviation form
- subtitle fragment

If the input is too sparse for the full minimum set, use every available major identifying field and say so in the output.

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

If multiple candidates remain plausible after verification, report the result as ambiguous instead of guessing.

If no candidate can be verified confidently, report not found or ambiguous, depending on the evidence.

### 5. Handle still-processing or inaccessible items

If a candidate exists in Page Index but is still processing, unavailable, or inaccessible:
- treat it as not found for the current task
- report the exact reason to the user
- do not count it as a successful match
- do not store it in the bridge mapping file

### 6. Update the bridge mapping

After a verified result:
- add or update the bibliography-to-filename mapping
- include all verified filenames when there are multiple true matches
- classify the multi-file relation as duplicate library copy, alternate version, or mixed verified set
- update outdated filenames when the stored mapping no longer reflects the current Page Index collection
- record a fresh verification date
- keep notes short and factual

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
- that a stored mapping existed but was treated only as a lead because it was incomplete, contradictory, or low-confidence
- that a candidate existed but was still processing or inaccessible
- that all reasonable Page Index-only search passes were exhausted
- that the input was too sparse to run the full minimum search pass set
- that duplicate input rows were grouped only because they matched exactly on the major identifying fields

## Non-Negotiable Rules

- Never search outside Page Index for this task.
- Never upload or process papers on your own initiative.
- Never treat a still-processing Page Index file as found.
- Never skip verification when multiple candidates exist.
- Never invent a bridge mapping location when `memory/pageindex/` is missing.
- Never collapse distinct bibliography entries into one mapping unless they match exactly on the major identifying fields.
- Never store a not-found, ambiguous, inaccessible, or still-processing item in the bridge mapping file.
