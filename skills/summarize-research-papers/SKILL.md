---
name: summarize-research-papers
description: Summarize one or more research papers into structured per-paper Markdown reports using a fixed paper-reading template. Use when the user's primary goal is the summary report itself and the paper content is already accessible, already extracted, attached, or has already been prepared by another source-specific workflow. Use this skill for the general report-writing standard, evidence discipline, and summary quality bar. Do not use it for paper finding, source-specific library resolution, coverage-only reading verification, classification, cross-paper synthesis, or Page Index-specific orchestration; if the request is specifically about summarizing papers from Page Index, use `pageindex-summarize-papers` for that wrapper workflow.
---

# Summarize Research Papers

## Overview

Create one structured Markdown summary report per paper from already-accessible paper content.

This skill owns the general summary-writing standard: template use, evidence discipline, page anchoring, one-paper-per-report output, and quality expectations. It does **not** own paper finding, source-specific resolution, or full-read verification mechanics.

## Example Prompts

- Summarize this paper into the standard Markdown report format.
- Write detailed reading notes for these two papers and save one Markdown file per paper.
- Turn this full paper into a structured memo with strengths, limitations, and follow-up questions.
- I already extracted the paper text; use it to create a proper paper summary report.

Do not use this skill for requests like:
- find this paper in Page Index
- verify whether every page was read
- classify this paper into the taxonomy
- compare these eight papers in one synthesis memo
- summarize this paper from Page Index

## Required Template

For every execution of this skill, read and use:
- `references/paper-summary-report-template.md`

Use that template as the report skeleton.

Template rules:
- Fill as many fields as the paper and available metadata support.
- Leave fields blank when the information is genuinely unavailable.
- Do **not** invent missing bibliographic facts, identifiers, datasets, code links, or venue details.
- Keep the section headings and field labels stable unless the user explicitly asks for a different format.

## Scope Boundaries

Use this skill for:
- per-paper summaries grounded in actual paper content
- batch requests where each paper should end up with its own report
- structured reading notes that follow the fixed report template
- writing the final report after another workflow has already handled paper access or full-read verification

Do not use this skill for:
- paper finding or bibliography resolution
- source-specific access workflows such as Page Index resolution
- page-coverage-only reading reports
- classification or taxonomy placement
- extracting only abstracts or metadata when the user asked for a real paper summary
- producing one blended summary for multiple papers
- cross-paper comparison, synthesis, or literature-review aggregation as the main output

## Input Sufficiency Rules

Before writing a real paper summary:
- confirm that the paper content is actually accessible in the current workflow
- distinguish between full-paper access and partial access
- match the summary claim to the evidence you truly have

When the user asked for a full paper summary:
- do not pretend that title, abstract, metadata, or document structure alone is enough
- if only partial paper content is available, say so clearly and either stop or produce a clearly limited partial summary if the user accepts that downgrade
- if another source-specific skill already established a full read, rely on that result instead of re-inventing the access workflow here

## Output Mode Rules

If the user wants files:
- write **one Markdown file per paper**
- update an existing report for the same paper instead of creating a near-duplicate unless the user explicitly wants versioned copies
- use a stable, human-legible filename when you control the filename

Preferred filename pattern:
- `<first-author-surname>-<year>-<short-title-slug>.md`

Filename rules:
- lowercase letters, digits, and hyphens only
- remove file-extension remnants and unsafe punctuation
- if core metadata is incomplete, fall back to a sanitized source filename stem
- avoid unnecessary duplicate suffixes like `-summary-report-report`

If the user did not ask for files:
- return the report directly in the assistant response unless another workflow specifies a destination

## Workflow

### 1. Normalize the request

For each requested paper:
- preserve user-visible order
- determine whether the user wants a reply-only summary or a saved Markdown file
- plan for a separate report per paper

### 2. Confirm the summary basis

Before writing:
- identify what paper source is available
- confirm whether the accessible content supports a full-paper summary or only a limited summary
- if the request depends on another workflow for retrieval or verification, let that workflow finish first

### 3. Read the template and draft from the paper

Once the paper content is available:
- read `references/paper-summary-report-template.md`
- use the paper itself as the source of record
- capture the paper's argument, method, evidence, results, limitations, and follow-up questions in the template
- keep claims anchored to what the paper actually says
- separate what the paper claims from what you think about it

### 4. Write one report per paper

For each paper:
- produce one complete report only for that paper
- do not merge different papers into a single report unless the user explicitly changed the task to synthesis
- if multiple source copies exist for the same paper, use one accessible copy as the primary reading source and note alternate versions when useful

### 5. Report the execution outcome

In the final response, include for each requested paper:
- original paper label or normalized reference
- whether the summary was based on full-paper access or limited access
- whether the report was written, updated, returned inline, or skipped
- output path when a file was written
- concise failure reason when skipped

## Content Guidance For The Report

### Bibliographic and identification fields

Use the best verified information available from the paper itself and trusted surrounding metadata.

Good sources include:
- title page
- first page
- header or footer cues when reliable
- trusted metadata provided by the current source workflow
- identifiers visible in the paper text

When uncertain:
- prefer leaving a field blank over guessing
- do not infer DOI, volume, issue, or page numbers from thin evidence

### Before Reading and Skim Snapshot sections

These sections should reflect honest reading stages.

If note-taking starts after the skim stage has already passed:
- reconstruct the skim-stage expectations conservatively from what would have been visible during a quick initial pass
- do not pretend that later understanding was already known at skim time

### During Reading and After Reading sections

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

Write this section from working memory after finishing the main read notes.

Rules:
- write 3-6 sentences
- do not immediately re-copy phrasing from the paper for this section
- aim for what actually stuck after reading
- if memory is weak, write a simpler and more cautious memory summary rather than inventing detail

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
- Never pretend that abstract-only or metadata-only access is a full paper summary.
- Never invent missing bibliographic metadata.
- Never collapse multiple papers into one report unless the user explicitly asked for synthesis instead.
- Never claim stronger source access than the workflow actually provided.
- Never treat Page Index-specific resolution or verification rules as part of this skill; use `pageindex-summarize-papers` when the request is specifically about Page Index.
