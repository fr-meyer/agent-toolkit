---
name: pageindex-summarize-papers
description: Summarize one or more papers stored in a Page Index collection into individual Markdown report files. Use when the request is specifically about Page Index papers and the workflow needs to resolve papers through `pageindex-find-papers`, verify full coverage through `pageindex-read-papers`, then write one summary file per fully read paper under a Page Index-oriented summary folder. This skill owns the Page Index-specific wrapper workflow only; once a paper has been resolved and fully read, use `summarize-research-papers` for the actual report-writing standard. Do not use this skill for general paper summarization outside Page Index, paper finding alone, coverage-only reading verification, classification, cross-paper synthesis, or a single combined summary for multiple papers.
---

# Page Index Summarize Papers

## Overview

Create one structured Markdown summary report per paper for papers stored in Page Index.

This skill owns only the Page Index-specific orchestration: resolution, full-read verification, and Page Index summary-folder rules. It does **not** own the general summary-writing standard. After a paper is resolved and fully read, use `summarize-research-papers` to produce the actual report content.

## Example Prompts

- Summarize this Page Index paper into the standard Markdown report format.
- Find these cited papers in Page Index, read them fully, and create one summary file per paper.
- Write structured reading notes for this paper from Page Index and save them under `memory/pageindex/summary/`.
- Make a detailed paper memo from this Page Index file using the standard report workflow.

Do not use this skill for requests like:
- summarize this local PDF into paper notes
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

## Scope Boundaries

Use this skill for:
- Page Index-specific per-paper summary workflows
- batch requests where each requested Page Index paper should end up with its own summary file
- orchestrating the handoff from Page Index resolution and full-read verification into the general summary-writing skill

Do not use this skill for:
- general paper summarization outside Page Index
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
- `summarize-research-papers` owns the actual report-writing standard once the paper is ready to summarize.
- Do not replace these dependencies with web search, local PDF search, OCR uploads, or external copies.
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

### 5. Hand off the report-writing step to `summarize-research-papers`

Once a paper has been resolved and fully read:
- use `summarize-research-papers` for the actual summary structure, evidence discipline, page anchoring, and quality bar
- treat the verified Page Index file as the paper source of record
- preserve any useful note about alternate verified Page Index versions when relevant
- keep one report per paper

### 6. Write the report file

When the summary content is ready:
- write it under the chosen Page Index summary folder
- use a stable, human-legible filename
- update an existing file for the same paper instead of creating a near-duplicate unless the user explicitly wants versioned copies

### 7. Final user-facing response

Report results directly in the assistant response.

For each requested paper, include:
- original paper reference or normalized label
- resolved Page Index filename used, when available
- whether the paper was fully read and therefore eligible for summary generation
- whether the summary file was written, updated, or skipped
- output file path when written or updated
- concise failure reason when skipped

## Never Do This

- Never perform fresh paper-finding logic inside this skill.
- Never skip `pageindex-find-papers` when the paper is unresolved.
- Never skip `pageindex-read-papers` when the user wants a real Page Index paper summary.
- Never write a full summary file for a paper that was not fully read.
- Never duplicate the general summary-writing instructions that belong in `summarize-research-papers`.
- Never collapse multiple papers into one report.
- Never invent missing bibliographic metadata.
- Never summarize from abstract-only or metadata-only access.
- Never store the report outside `memory/pageindex/summary/` unless the user explicitly changes the target location.
- Never silently create duplicate files for the same paper when an in-place update would do.
