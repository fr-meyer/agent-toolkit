---
name: pageindex-read-papers
description: Read one or more papers already resolved to verified Page Index files, with strict full-page coverage verification. Use when the user wants the agent to read papers stored in a Page Index collection all the way through, rather than only inspecting metadata, document structure, abstracts, or selected pages. This skill does not perform paper-finding; if the requested papers are not already resolved, first use pageindex-find-papers.
---

# Page Index Read Papers

## Overview

Read one or more papers stored in a Page Index collection from page 1 through page N, then verify that every page was actually read. This skill starts only after the requested papers have already been resolved to verified Page Index files.

Use this skill only for full-document reading through Page Index, not for paper-finding, metadata inspection, structure-only review, abstract-only review, or selected-page reading.

## Example Prompts

- Read this verified Page Index file all the way through and verify that every page was covered: <filename>
- Read these verified Page Index files from page 1 through page N and report page coverage for each one.
- After resolving these papers with `pageindex-find-papers`, read each verified Page Index file fully and tell me which ones were fully read and which ones were partial.
- Do not stop at the structure or abstract; once the paper is resolved, I want a full read of the verified Page Index file.

## Prerequisites and Operational Rules

- Page Index MCP tools must be available in the current runtime.
- If Page Index MCP tools are unavailable, stop and tell the user clearly.
- Use only Page Index tools that inspect documents already stored in the collection.
- Read each paper only through the verified copy stored in Page Index.
- Use `pageindex-find-papers` as the only paper-resolution path.
- If the requested papers are not already resolved to verified Page Index files or verified Page Index mappings, stop this reading workflow, run `pageindex-find-papers`, and continue only with its verified outputs.
- Do not duplicate paper-resolution logic from `pageindex-find-papers` inside this skill.
- Do not reproduce its direct-filename verification rules, search-pass rules, bridge-mapping workflow, or conservative match-verification process here; rely on that skill for paper resolution.
- Do not use web search, external PDFs, local filesystem copies, or alternate sources to fill gaps.
- Do not treat metadata, document structure, abstract-only reads, or first-page reads as equivalent to reading the paper.
- If the runtime cannot retrieve readable page content from Page Index, stop and report failure clearly.
- If a Page Index item is still processing, unavailable, or inaccessible, report failure for that paper clearly.
- If the runtime reads page content in batches, keep explicit page-number accounting so every page in every batch is tracked individually.

## Success Rule

- The **overall request succeeds only if every requested paper was first resolved to a verified Page Index file and every page of every requested paper was then read and verified**.
- Otherwise, the **overall request fails**.

## Inputs To This Skill

This skill should operate on resolved paper targets only, such as:
- verified Page Index filenames
- verified Page Index mappings
- verified outputs returned by `pageindex-find-papers`

If the requested papers are not yet resolved, use `pageindex-find-papers` first.

## Required Workflow

### 1. Require resolved paper targets

Before starting the read:

- confirm that each requested paper is already resolved to a verified Page Index file
- if not, use `pageindex-find-papers` first
- preserve user-visible paper order throughout the workflow and final output

If any requested paper remains unresolved after that step:
- report the unresolved outcome from `pageindex-find-papers`
- do not continue reading that paper
- treat the overall request outcome as failure

### 2. Establish the coverage target

Before claiming any full read:

- retrieve the document's total page count
- record that page count explicitly for the current paper
- treat that page count as the required coverage target

If the total page count cannot be determined reliably:
- report failure for that paper clearly
- do not claim a full read

If the Page Index item is still processing, unavailable, or inaccessible at this stage:
- stop the read for that paper
- report the exact state clearly
- mark the paper as `inaccessible`
- do not claim a full or partial read unless actual page content was retrieved

### 3. Read every page in the paper

Read the paper from page 1 through page N.

Required behavior:
- read **all pages from 1..N**
- do not skip appendices, references, supplements embedded in the document, or figure-heavy pages
- do not stop after the introduction, methods, or conclusion
- do not replace page reads with a structure-only lookup
- do not assume a page was read because adjacent pages were read successfully

Maintain an explicit page coverage record while reading, including at least:
- pages successfully read
- pages failed
- pages retried
- pages still missing after retry

### 4. Reconcile coverage and retry missing pages

After the first pass:

- compare the successfully read pages against the total page count
- verify that the intended coverage is the full set `1..N`
- identify every missing or failed page explicitly

If any page is missing or failed:
- retry those pages
- update the coverage record

If any page still cannot be read after retry:
- mark the paper as `partial` if some pages were read but coverage is incomplete
- mark the paper as `inaccessible` if readable page content could not be retrieved at all or became unavailable during reading
- report exactly which pages were unread or failed
- treat the overall request outcome as failure

### 5. Run a second verification pass

Before finalizing any `fully read` result:

- re-check that `pages_read_count == total_page_count`
- re-check that every page number from `1..N` is present in the verified set of successfully read pages
- re-check that no failed pages remain hidden inside a range summary
- if batched reads were used, verify that every page inside every batch was actually covered

This verification pass exists to prevent false claims of full coverage.

### 6. Report reading coverage only

Once coverage status is known:

- report only the reading and verification results
- state which paper was read, how many pages it contains, which pages were successfully read, and which pages were missed or failed
- do not summarize the paper's content
- do not interpret the paper's content
- do not expand this skill into analysis, extraction, or classification

## Multi-Paper Rules

When reading multiple papers:

- process each paper independently
- keep user-visible order
- track coverage separately for each paper
- do not let a successful read of one paper hide failures in another
- report each paper with its own final status and coverage

## Required Output

The expected output of this skill is the user-facing response only.

- Do not create `.txt`, `.md`, `.json`, or other files to store the reading report unless the user explicitly requests file creation as a separate task.
- Do not write the output to disk by default.
- Report the result directly in the assistant response.

Always provide three levels of output.

### A. Overall Request Outcome

State the overall request outcome explicitly.

- `success` means **every requested paper was resolved to a verified Page Index file and every page of every requested paper was read and verified**
- otherwise the outcome is `failure`

When the outcome is `failure`, give a concise reason.

### B. Coverage Summary

Give a concise, scan-friendly summary for all requested papers.

For each paper, include:
- paper label or bibliography entry
- verified Page Index filename when available
- status: `fully read`, `partial`, `inaccessible`, or a delegated resolution outcome from `pageindex-find-papers` such as `not found` or `ambiguous`
- page coverage in the form `X/Y pages`
- short failure note when relevant

### C. Detailed Per-Paper Report

For each paper, include:
- original paper reference or short normalized label
- verified Page Index filename or filenames used
- total page count
- pages successfully read
- pages missed, failed, or inaccessible
- whether second-pass verification succeeded
- final per-paper status
- a clear statement of whether the full paper was read completely

Do not include a summary of the paper's contents.
Do not include interpretation of the paper's contents.

## Required Wording Discipline

- Say **"fully read"** only when all pages were read and verified.
- Say **"partial"** only when some pages were read but coverage is incomplete.
- Say **"not found"** or **"ambiguous"** only when those outcomes were returned by `pageindex-find-papers` during the resolution stage.
- Say **"inaccessible"** only when the resolved Page Index file exists but readable page content could not be retrieved during the read process.
- Do not report overall `success` unless all requested papers were resolved and fully read.

Preferred phrasing:
- `Overall request outcome: success`
- `Overall request outcome: failure`
- `Fully read: 12/12 pages verified`
- `Partial: 9/12 pages read; pages 10-12 unavailable`
- `Not found: paper could not be resolved in Page Index`
- `Inaccessible: paper exists in Page Index but readable page content could not be retrieved`

## Recommended Output Shape

```md
## Overall Request Outcome
- Outcome: failure
- Reason: 1 of 3 requested papers could not be fully read

## Coverage Summary
- Paper 1: fully read — 12/12 pages — <filename>
- Paper 2: partial — 9/12 pages — pages 10-12 failed
- Paper 3: not found

## Detailed Report
### Paper 1 — <label>
- Page Index file: <filename>
- Coverage: 12/12 pages
- Pages successfully read: 1-12
- Verification: second-pass coverage check passed
- Final status: fully read
- Full paper read completely: yes

### Paper 2 — <label>
- Page Index file: <filename>
- Coverage: 9/12 pages
- Pages successfully read: 1-9
- Missing pages: 10, 11, 12
- Verification: failed
- Final status: partial
- Full paper read completely: no
```

## Never Do This

- Never perform paper-finding logic inside this skill.
- Never stop at document structure when the task is to read the paper.
- Never read only a subset of pages unless the user explicitly asked for that.
- Never claim that the full paper was read without full page coverage verification.
- Never silently ignore failed pages.
- Never report an overall success unless every requested paper was resolved and every page of every requested paper was read and verified.
- Never create a report file on disk unless the user explicitly asks for that as a separate task.
- Never summarize or interpret the paper's content as part of this skill.
- Never merge multiple papers into one combined coverage record.
- Never use non-Page-Index sources to complete a paper unless the user explicitly changes the task.
- Never skip `pageindex-find-papers` when the requested paper is not already resolved.
