---
name: pageindex-ingest-paper-urls
description: Use this skill when the user needs to ingest one or more direct fetchable PDF URLs into Page Index, especially when they ask to submit papers, add PDFs to Page Index, or process URLs after checking for duplicates. Apply it when requests involve fetchable PDF URLs, Page Index submission, or URL-based ingestion workflows with no Zotero-specific discovery step. Do not use it for paper finding alone, reading existing Page Index papers, summarization, Zotero attachment exports or manifests, local file paths, or non-Page-Index upload workflows.
---

# Page Index Ingest Paper URLs

## Goal

Ingest fetchable PDF URLs into Page Index with a conservative duplicate check first.

## When to use

Use this skill when the user already has one or more **direct fetchable PDF URLs** and wants them added to Page Index.

Use it for:
- URL-based Page Index ingestion
- adding papers after a duplicate check
- workflows that will later feed Page Index reading or summarization skills

Do not use it for:
- finding papers already in Page Index
- reading or summarizing papers already in Page Index
- Zotero attachment exports, Zotero manifests, or zotero_file_url sources
- local PDF paths
- attachment bytes or filesystem uploads
- non-Page-Index upload targets

## Required workflow

1. For each URL, inspect the source filename or any user-provided paper metadata.
2. Run `pageindex-find-papers` first when there is any useful filename/title/citation hint, and treat likely matches conservatively.
3. If a verified duplicate exists, stop and report the match instead of ingesting again.
4. If the caller handed this skill an authenticated fetch URL from another workflow, treat that URL as runtime-only sensitive input. Do not persist it or echo it raw.
5. If no verified duplicate is found, submit the fetchable PDF URL with `pageindex__process_document`.
6. Report the resulting Page Index document status or any ingestion failure clearly, redacting sensitive query parameters when present.

## Gotchas

- This skill is URL-only. Do not accept local file paths here.
- Do not assume a URL is fetchable just because it looks like a PDF link.
- Treat query-string credentials as sensitive. If an authenticated URL is supplied by another workflow, do not store it and do not surface it without redaction.
- If the user only has a filename, citation, or title, resolve that first with `pageindex-find-papers` before ingesting anything.
- If the user needs Zotero attachments, Zotero attachment manifests, or `zotero_file_url` sources, use `zotero-docai-ingest-to-pageindex` instead.

## Output expectations

When the ingest succeeds, return:
- the ingested URL only if it is non-sensitive or safely redacted
- the Page Index document identifier or result summary
- whether duplicate checking was performed

When the ingest is blocked, return:
- the reason
- the likely duplicate or missing input that caused the block
- any sensitive URL only in redacted form
