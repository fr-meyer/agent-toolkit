---
name: zotero-docai-ingest-to-pageindex
description: Use this skill when the user needs to turn Zotero-derived PDF sources into Page Index ingests, especially from zotero_file_url exports, Zotero attachment manifests, or zotero-docai-pipeline discovery outputs. Apply it when requests involve Zotero-backed batches of PDFs that should end up in Page Index, even if the user does not mention Page Index skill names. Do not use it for direct public PDF URLs with no Zotero context, direct Zotero PDF download, Page Index reading or summarization, local PDF paths without exported URLs, or Page Index ingestion that is already URL-only and does not involve Zotero.
---

# Zotero DocAI Ingest to Page Index

## Goal

Bridge Zotero-derived PDF sources into Page Index using the existing URL ingest workflow.

This skill is a Zotero-focused wrapper around `pageindex-ingest-paper-urls`.
Use `pageindex-ingest-paper-urls` for the actual Page Index submission step.

This skill owns the Zotero-specific authenticated URL handoff policy for downstream MCP-style URL ingestion.
That includes when to transform a plain `zotero_file_url` into an authenticated fetch URL and how to do that safely.

## When to use

Use this skill when the user already has, or can produce, Zotero-derived attachment URLs or manifests such as:
- `zotero_file_url` values exported from `zotero-docai-pipeline`
- a Zotero attachment manifest containing file URLs
- a batch of Zotero attachment URLs intended for Page Index

Use it for:
- Zotero attachment export workflows
- `zotero-docai-pipeline` discovery exports that include source URLs
- turning Zotero PDF sources into Page Index ingests

Do not use it for:
- direct Zotero PDF download only
- Page Index paper finding only
- Page Index reading, coverage checks, or summarization
- local PDF paths without an exported URL or manifest
- non-Zotero URL ingestion that should go straight to `pageindex-ingest-paper-urls`

## Required workflow

1. Confirm the user is working from Zotero-derived PDF source URLs or a `zotero-docai-pipeline` export/manifest.
2. If the user only has paper metadata such as title, filename, or citation, run `pageindex-find-papers` first to check whether the paper already exists in Page Index.
3. Normalize the Zotero source into direct plain `zotero_file_url` values.
4. If the Zotero URLs are not publicly fetchable, construct authenticated fetch URLs only at the handoff step using Zotero's supported query-parameter auth form:
   - `https://api.zotero.org/.../file?key=<ZOTERO_PAGEINDEX_FETCH_KEY>`
5. Prefer a dedicated read-only key for this transformation, exposed separately from the user's broader automation key.
6. Do not persist the authenticated URLs to manifests, summaries, retry files, or logs. Persist only the plain `zotero_file_url` values.
7. Hand only the runtime-authenticated fetch URL(s) to `pageindex-ingest-paper-urls` for the actual Page Index submission step.
8. Report which URLs were accepted, which were blocked, and whether any likely duplicate was already found in Page Index.

## Gotchas

- This skill does not invent Zotero URLs; it expects exported or otherwise supplied Zotero attachment URLs.
- Plain Zotero attachment URLs are often not directly fetchable by Page Index. For private access, use Zotero's query-string auth only at runtime handoff.
- Use a dedicated read-only key such as `ZOTERO_PAGEINDEX_FETCH_KEY` for runtime handoff when possible. Do not default casually to a broader read/write key.
- Do not write key-bearing URLs to disk.
- Do not echo raw key-bearing URLs in logs, reports, or surfaced errors. Redact query-string credentials if a URL must be shown.
- Direct public PDF URLs with no Zotero context should use `pageindex-ingest-paper-urls` directly rather than this wrapper.
- Downloading from Zotero to disk or sending PDFs to another OCR provider belongs to `zotero-docai-pipeline`, not this skill.

## Output expectations

When successful, report:
- the Zotero source that was used
- the resolved plain `zotero_file_url` values
- whether duplicate checking was done
- the Page Index ingest result for each URL

When blocked, report:
- which Zotero source was missing or unusable
- whether the blocker was a missing export/manifest, a likely duplicate, or an unreachable URL
- never include raw key-bearing URLs in the surfaced output
