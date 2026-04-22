---
name: pageindex-ingest-paper-urls
description: Use this skill when the user needs to ingest one or more public PDF URLs into Page Index, especially when they ask to submit papers, add PDFs to Page Index, or process URLs after checking for duplicates. Apply it when requests involve public PDF URLs, Page Index submission, or URL-based ingestion workflows. Do not use it for paper finding alone, reading existing Page Index papers, summarization, local file paths, or non-Page-Index upload workflows.
---

# Page Index Ingest Paper URLs

## Goal

Ingest public PDF URLs into Page Index with a conservative duplicate check first.

## When to use

Use this skill when the user already has one or more **public PDF URLs** and wants them added to Page Index.

Use it for:
- URL-based Page Index ingestion
- adding papers after a duplicate check
- workflows that will later feed Page Index reading or summarization skills

Do not use it for:
- finding papers already in Page Index
- reading or summarizing papers already in Page Index
- local PDF paths
- attachment bytes or filesystem uploads
- non-Page-Index upload targets

## Required workflow

1. For each URL, inspect the source filename or any user-provided paper metadata.
2. Run `pageindex-find-papers` first when there is any useful filename/title/citation hint, and treat likely matches conservatively.
3. If a verified duplicate exists, stop and report the match instead of ingesting again.
4. If no verified duplicate is found, submit the public PDF URL with `pageindex__process_document`.
5. Report the resulting Page Index document status or any ingestion failure clearly.

## Gotchas

- This skill is URL-only. Do not accept local file paths here.
- Do not assume a URL is public just because it looks like a PDF link.
- If the user only has a filename, citation, or title, resolve that first with `pageindex-find-papers` before ingesting anything.
- If the user needs Zotero attachments or local files, use a separate Zotero-focused skill instead.

## Output expectations

When the ingest succeeds, return:
- the URL ingested
- the Page Index document identifier or result summary
- whether duplicate checking was performed

When the ingest is blocked, return:
- the reason
- the likely duplicate or missing input that caused the block
