---
name: pageindex-summarize-papers
description: Summarize one or more papers stored in a Page Index collection into individual Markdown report files using a fixed paper-reading template. Use when the user wants structured per-paper reading notes, paper memos, or summary reports saved under `memory/pageindex/summary/`, especially when the paper may be referenced by a verified Page Index filename, a bibliography entry, a citation, or messy free-form reference text. Apply it when requests involve summarizing a paper, writing a paper report, making detailed reading notes, or producing one report per paper from Page Index. Resolve papers only through `pageindex-find-papers`, require full-paper coverage through `pageindex-read-papers`, and write one report file per successfully read paper. Do not use this skill for paper-finding alone, coverage-only reading, classification, cross-paper synthesis, or a single combined summary for multiple papers.
---

# Page Index Summarize Papers

## Overview

Create one structured Markdown summary report per paper for papers stored in Page Index.

This skill does **not** own paper finding and does **not** own full-document coverage verification. Use `pageindex-find-papers` for resolution and `pageindex-read-papers` for full-paper reading with page-coverage verification, then produce the summary report only after a paper has been fully read.

## Example Prompts

- Summarize this Page Index paper into the standard Markdown report format.
- Find these cited papers in Page Index, read them fully, and create one summary file per paper.
- Write structured reading notes for this paper and save them under `memory/pageindex/summary/`.
- Make a detailed paper memo from this Page Index file using the fixed template.

Do not use this skill for requests like:
- just find this paper in Page Index
- tell me whether this paper was fully read
- classify this paper into the taxonomy
- compare these five papers in one synthesis memo

## Required Output Location

Preferred output folder:
- `memory/pageindex/summary/`

Rules:
- If `memory/pageindex/summary/` does not exist, do not silently create it.
- Ask the user whether that folder should be created or whether another existing path should be used because it already contains or should contain those summary documents.
- Do not infer a substitute path on your own.
- Write **one Markdown file per paper**.
- Do not merge multiple papers into one combined summary file.
- If a report file for the same paper already exists, update that file instead of creating a near-duplicate unless the user explicitly asks for versioned copies.

## Required Template

For every execution of this skill, read and use:
- `references/paper-summary-report-template.md`

Use that template as the report skeleton.

Template rules:
- Fill as many fields as the paper and the available metadata support.
- Leave fields blank when the information is genuinely unavailable.
- Do **not** invent missing bibliographic facts, identifiers, datasets, code links, or venue details.
- Keep the section headings and field labels stable unless the user explicitly asks for a different format.

## Scope Boundaries

Use this skill for:
- per-paper summaries grounded in a full read of papers already stored in Page Index
- batch requests where each requested paper should end up with its own summary file
- structured reading notes that follow the fixed report template

Do not use this skill for:
- paper finding by itself
- page-coverage-only reading reports
- classification or taxonomy placement
- extracting only abstracts or metadata
- producing one blended summary for multiple papers
- cross-paper comparison, synthesis, or literature-review aggregation as the main output

## Dependencies and Hard Boundaries

- Page Index MCP tools must be available in the runtime.
- `pageindex-find-papers` is the only allowed paper-resolution path.
- `pageindex-read-papers` is the required full-read verification path.
- Do not replace either dependency with web search, local PDF search, OCR uploads, or external copies.
- Do not summarize a paper from title, abstract, metadata, or structure alone when the user asked for a paper summary.
- Do not claim that a paper was summarized from a full read unless `pageindex-read-papers` established full coverage.
- If a paper cannot be resolved or cannot be fully read, report that clearly and do not write a misleading full summary for that paper.

## Workflow

### 1. Normalize the request

For each requested paper:
- preserve the user-visible order
- determine whether the paper is already provided as a verified Page Index file or still needs resolution
- plan for a separate output file per paper

### 2. Confirm the output folder

Before writing any summary files:
- check that `memory/pageindex/summary/` exists
- if it does not exist, ask the user whether to create it or whether another existing path should be used because it already contains or should contain those summary documents
- do not silently create the folder
- do not infer an alternate path on your own
- if the chosen folder cannot be created or written, stop and report the exact block

### 3. Resolve papers only through `pageindex-find-papers`

If any requested paper is not already resolved to a verified Page Index file:
- use `pageindex-find-papers`
- accept only its verified outputs
- preserve any exact `not found`, `ambiguous`, or inaccessible outcomes it returns

If resolution fails for a paper:
- do not continue to a summary for that paper
- report the failure clearly in the final response

### 4. Require full reading through `pageindex-read-papers`

For each resolved paper:
- use `pageindex-read-papers`
- require a `fully read` outcome with verified page coverage
- do not treat `partial`, `inaccessible`, `not found`, or `ambiguous` as sufficient for summary generation

If the paper was not fully read:
- do not produce a normal final summary report for that paper
- tell the user why the summary file was not created

### 5. Summarize only after the full read is established

Once a paper has been fully read:
- base the report on the full-paper reading, not on skim impressions alone
- use the verified Page Index file as the paper source of record
- capture the paper's argument, method, evidence, results, limitations, and follow-up questions in the template
- keep claims anchored to what the paper actually says
- separate what the paper claims from what you think about it

If multiple verified Page Index files exist for the same paper:
- choose one accessible verified copy as the primary reading source
- note alternate or duplicate verified versions in `Related versions` or the surrounding notes when useful
- do not merge different papers just because their titles are similar

### 6. Write the report file

Use a stable filename derived from the paper identity.

Preferred filename pattern:
- `<first-author-surname>-<year>-<short-title-slug>.md`

Filename rules:
- lowercase letters, digits, and hyphens only
- remove file-extension remnants and unsafe punctuation
- keep the filename human-legible
- if core metadata is incomplete, fall back to a sanitized verified Page Index filename stem
- avoid unnecessary duplicate suffixes like `-summary-report-report`

Each file must contain one complete report for one paper only.

### 7. Final user-facing response

Report results directly in the assistant response.

For each requested paper, include:
- original paper reference or normalized label
- resolved Page Index filename used, when available
- whether the paper was fully read and therefore eligible for summary generation
- whether the summary file was written, updated, or skipped
- output file path when written or updated
- concise failure reason when skipped

## Content Guidance For The Report

### Bibliographic and identification fields

Use the best verified information available from the paper itself and its Page Index metadata.

Good sources include:
- title page
- first page
- header/footer cues when reliable
- publisher metadata visible in Page Index
- identifiers visible in the paper text

When uncertain:
- prefer leaving a field blank over guessing
- do not infer DOI, volume, issue, or page numbers from thin evidence

### Before Reading and Skim Snapshot sections

These sections should still be filled in, but they must reflect honest reading stages.

If the workflow already moved beyond the skim stage before formal note-taking began:
- reconstruct the skim-stage expectations conservatively from what would have been visible during a quick initial pass
- do not pretend that a later understanding was already known at skim time

### During Reading and After Reading sections

These should reflect the actual full-paper reading.

Prioritize:
- central question
- main claim
- contribution type
- method or argumentative structure
- strongest evidence
- major results or takeaways
- limitations, cautions, and unresolved questions

When highlighting a claim, contribution, result, limitation, definition, or especially important passage:
- include the most precise page number or tight page range you can recover from the paper
- prefer `p. X` for a single page and `pp. X-Y` for a short range
- keep the page anchor close to the statement it supports so later searching is easier
- do not invent page numbers when the source location is uncertain

### Summary From Memory section

This section must be written from working memory after finishing the main read notes.

Rules:
- write 3-6 sentences
- do not immediately re-copy phrasing from the paper for this section
- aim for what actually stuck after reading
- if your memory is weak, write a simpler, more cautious memory summary rather than inventing detail

### One-Line Verdict section

Write one sentence capturing the single most important thing worth remembering about the paper.

Prefer:
- the strongest durable contribution
- the clearest methodological lesson
- the most reusable conceptual distinction

Avoid vague verdicts like:
- `interesting overview`
- `useful paper`
- `good results`

## Quality Bar

A good report should make it possible for the user to:
- remember what the paper is about
- understand what the paper actually contributes
- see how convincing the paper was
- identify limitations and next reads
- reuse the report later without reopening the paper immediately

## Never Do This

- Never perform fresh paper-finding logic inside this skill.
- Never skip `pageindex-find-papers` when the paper is unresolved.
- Never skip `pageindex-read-papers` when the user wants a real paper summary.
- Never write a full summary file for a paper that was not fully read.
- Never collapse multiple papers into one report.
- Never invent missing bibliographic metadata.
- Never summarize from abstract-only or metadata-only access.
- Never store the report outside `memory/pageindex/summary/` unless the user explicitly changes the target location.
- Never silently create duplicate files for the same paper when an in-place update would do.
