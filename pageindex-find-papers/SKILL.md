---
name: pageindex-find-papers
description: Resolve one or more papers to verified Page Index files using only the existing Page Index collection. Use when the user provides direct Page Index filenames, bibliography references, citations, or messy free-form reference text and the agent needs to determine which Page Index file or files should be treated as the correct resolved papers for later reading or analysis. Verify matches conservatively, treat still-processing or inaccessible items as not found, and maintain a verified bibliography-to-Page-Index bridge mapping for reuse.
---

# Page Index Find Papers

## Overview

Resolve one or more requested papers to verified Page Index files using only the existing Page Index collection. This skill owns all paper resolution inside Page Index, whether the user starts from a direct Page Index filename, a verified mapping, or bibliography-like input.

Use this skill before any later skill that needs resolved Page Index files for reading, extraction, analysis, or classification.

## Hard Boundaries

- Use only Page Index MCP tools.
- Use only Page Index capabilities that inspect the existing collection: search, listing, lookup, metadata retrieval, and content reading.
- Do not use web search, OCR tools, local file search, or any non-Page-Index retrieval method for this task.
- Do not upload, ingest, process, or add papers to Page Index unless the user explicitly requests that as a separate action.
- Treat still-processing, unavailable, or inaccessible Page Index items as not found for the current task.
- If Page Index MCP tools are unavailable in the current runtime, stop and tell the user clearly.

## Input Types

Handle either of these:

1. **Direct Page Index targets**
   - Page Index filename
   - already-verified Page Index mapping
   - any user-supplied Page Index file reference that can be checked directly against the collection

2. **Bibliography-like targets**
   - bibliography entries
   - citations
   - messy free-form reference text
   - paper title + authors + year

## Required Preflight

Before doing fresh bibliography-style Page Index search work, check the bridge mapping location first.

Preferred folder:
- `memory/pageindex/`

Recommended file:
- `memory/pageindex/bibliography-to-pageindex-bridge.md`

Rules:
- If `memory/pageindex/` does not exist, do not infer a substitute path.
- Ask the user whether to create `memory/pageindex/` or whether another existing path should be used.
- This first-run pause is intentional. Do not start fresh bibliography-style Page Index searching until that location question is resolved.
- If the bridge mapping file exists, consult it first.

## Bridge Mapping File

Use the bridge mapping file to store only successfully found and verified papers.

Major identifying fields means, at minimum:
- normalized title
- first author surname
- publication year

Use additional evidence such as second author, source, subtitle, acronym, or visible content when needed to resolve ambiguity.

Rules:
- Store only successfully found and verified papers.
- Do not store not-found papers.
- Do not store ambiguous candidates.
- Do not store inaccessible or still-processing files.
- If a mapping exists, verify that each mapped file still exists and is accessible before trusting it.
- Even when a mapped file exists and is accessible, do a light re-verification against the major identifying fields before treating it as valid.
- If a stored mapping is incomplete, contradictory, low-confidence, or malformed, do not treat it as authoritative. Use it only as a search lead, then verify normally.
- If a stored mapping is outdated, update it.
- If multiple Page Index files truly match the same bibliography entry, record all verified files.
- For multiple verified files, distinguish between duplicate library copies, alternate versions, and mixed verified sets in the notes.
- Merge bibliography rows only when they match exactly on the major identifying fields.
- Do not merge near-matches or uncertain duplicates.
- If an old mapped filename no longer exists or is no longer accessible, do not silently keep it as valid.

### Recommended entry shape

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

## Batch Rules

When the user provides multiple targets in one request:
- preserve the user-visible order in the final output
- process each target independently
- if two request rows are exact duplicates on the major identifying fields, you may reuse the same verified resolution result
- if two rows are only similar, keep them separate unless the duplication is exact on the major identifying fields
- if one verified search result resolves multiple truly identical references, say so explicitly in the output

## Workflow

### 1. Classify the target type

For each requested target, decide whether it is:
- a direct Page Index target, or
- a bibliography-like target

Preserve the user-visible order throughout the workflow and final output.

### 2. Resolve direct Page Index targets

If the user supplied a direct Page Index filename or already-verified Page Index mapping:
- verify that the referenced file still exists in Page Index
- verify that it is accessible
- do a light verification that the target is the intended paper when enough identifying information is available
- if the file is still valid, treat the paper as found

If the direct target does not exist, is inaccessible, or cannot be trusted as the intended paper:
- report the exact failure reason
- treat it as `not found` or `ambiguous`, depending on the evidence
- do not silently accept it as resolved

If a direct target is still processing, unavailable, or inaccessible:
- treat it as not found for the current task
- report the exact reason
- do not store it in the bridge mapping file

### 3. Normalize bibliography-like references

For each bibliography-like target:
- isolate the likely title
- isolate the main author surname or surnames
- isolate the publication year
- note any distinctive journal, conference, subtitle, acronym, or uncommon title token

Do not over-trust formatting. Bibliography text may be noisy, incomplete, or inconsistent.

### 4. Check the bridge mapping first

If a bridge mapping file exists:
- look for an exact or highly confident match to the bibliography entry
- use the mapped filename as the first verification target
- verify that the mapped file is still present and accessible in Page Index
- lightly re-verify the mapped file against title, first author surname, and year before treating it as resolved

If the mapping resolves the paper and the file is accessible, treat the paper as found and say that the mapping file resolved it.

### 5. Search Page Index with mostly single-keyword passes

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

### 6. Verify candidates conservatively

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

### 7. Handle still-processing or inaccessible items

If a candidate exists in Page Index but is still processing, unavailable, or inaccessible:
- treat it as not found for the current task
- report the exact reason to the user
- do not count it as a successful match
- do not store it in the bridge mapping file

### 8. Update the bridge mapping

After a verified bibliography-based result:
- add or update the bibliography-to-filename mapping
- include all verified filenames when there are multiple true matches
- classify the multi-file relation as duplicate library copy, alternate version, or mixed verified set
- update outdated filenames when the stored mapping no longer reflects the current Page Index collection
- record a fresh verification date
- keep notes short and factual

Keep the mapping conservative, reusable, and easy to audit later.

Direct filename verification does not require creating a new bridge entry unless there is also a bibliography-like reference worth preserving.

## Output Requirements

For each requested target, report:
- the original target text or a short normalized version of it
- status: `found`, `found via bridge mapping`, `ambiguous`, or `not found`
- matched Page Index filename or filenames when found
- concise verification notes explaining why the resolution is correct
- exact failure reason when not found, still processing, or inaccessible

When relevant, say explicitly:
- that the target was a direct Page Index filename or mapping and was verified directly
- that the bridge mapping file was checked first
- that the stored mapping was still valid
- that the stored mapping was outdated and was updated
- that a stored mapping existed but was treated only as a lead because it was incomplete, contradictory, or low-confidence
- that a candidate existed but was still processing or inaccessible
- that all reasonable Page Index-only search passes were exhausted
- that the input was too sparse to run the full minimum search pass set
- that duplicate input rows were grouped only because they matched exactly on the major identifying fields

## Never Do This

- Never search outside Page Index for this task.
- Never upload or process papers on your own initiative.
- Never treat a still-processing Page Index file as found.
- Never skip verification when multiple candidates exist.
- Never invent a bridge mapping location when `memory/pageindex/` is missing.
- Never collapse distinct bibliography entries into one mapping unless they match exactly on the major identifying fields.
- Never store a not-found, ambiguous, inaccessible, or still-processing item in the bridge mapping file.
- Never accept a user-supplied direct filename as resolved without verifying that it still exists and is accessible in Page Index.
