---
name: zotero-docai-ingest-to-pageindex
description: Use this skill when the user needs to turn Zotero-derived PDF sources into Page Index ingests, especially from zotero_file_url exports, Zotero attachment manifests, or zotero-docai-pipeline discovery outputs. Apply it when requests involve Zotero-backed batches of PDFs that should end up in Page Index, even if the user does not mention Page Index skill names. Do not use it for direct public PDF URLs with no Zotero context, direct Zotero PDF download, Page Index reading or summarization, local PDF paths without exported URLs, or Page Index ingestion that is already URL-only and does not involve Zotero.
---

# Zotero DocAI Ingest to Page Index

## Goal

Bridge Zotero-derived PDF sources into Page Index using a Zotero-derived URL ingest workflow while preserving the Zotero attachment filename as the canonical ingest filename.

This skill is a Zotero-focused wrapper around `pageindex-ingest-paper-urls`.
Use `pageindex-ingest-paper-urls` for the actual Page Index submission step.

## When to use

Use this skill when the user already has, or can produce, Zotero-derived attachment URLs or manifests such as:
- `zotero_file_url` values exported from `zotero-docai-pipeline`
- authenticated Zotero attachment URLs derived from a Zotero export flow
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

## Required policy

- Treat the Zotero attachment filename as the canonical ingest filename.
- Preserve that filename when submitting the document to Page Index whenever the selected ingest method supports it.
- For this Zotero → Page Index workflow, Page Index submission must use the Page Index MCP path only, via `pageindex-ingest-paper-urls` / Page Index MCP tools.
- Do not use direct Page Index API, SDK, HTTP multipart upload, custom upload clients, or API-key-based Page Index upload code unless Franck explicitly overrides this rule.
- If MCP-only ingestion cannot fetch the URL or preserve the canonical Zotero filename, stop and report the blocker; do not implement an API workaround.
- Do not silently accept degraded naming such as `file.pdf` when the Zotero attachment filename is available.
- If the current ingest method cannot preserve the filename, stop and report the limitation clearly instead of calling the ingest a full success.
- Do not assume that a plain `zotero_file_url` is directly fetchable by Page Index.
- Distinguish clearly between:
  - a plain Zotero file URL
  - an authenticated Zotero attachment URL
  - a publicly reachable direct PDF URL

## Required workflow

1. Confirm the user is working from Zotero-derived PDF source URLs or a `zotero-docai-pipeline` export/manifest.
2. If the user only has paper metadata such as title, filename, or citation, run `pageindex-find-papers` first to check whether the paper already exists in Page Index.
3. Extract the Zotero attachment filename and treat it as the canonical ingest filename.
4. Normalize the Zotero source into the actual ingestable URL form:
   - use a plain `zotero_file_url` only if it is truly fetchable by the ingest target
   - use an authenticated Zotero attachment URL when the plain Zotero file URL is not fetchable and authenticated access is the intended bridge
   - do not treat a non-fetchable Zotero URL as ingestion-ready
5. Verify that the chosen URL is fetchable by the selected ingest path before calling the Page Index submission step.
6. Verify that the selected ingest method can retain the canonical Zotero filename in Page Index.
7. Hand the resulting URL to `pageindex-ingest-paper-urls` for the actual Page Index submission step only if both conditions hold:
   - the URL is fetchable
   - filename preservation remains intact
8. After submission, verify the resulting Page Index document name when needed to confirm that filename preservation actually held.
9. Report which URLs were accepted, which were blocked, whether any likely duplicate was already found in Page Index, whether fetchability was verified, and whether filename preservation was verified.

## Gotchas

- MCP-only is a hard constraint for this workflow. Do not bypass MCP filename or fetchability limits with direct Page Index API/SDK upload code unless Franck explicitly changes the constraint.
- This skill does not invent Zotero URLs; it expects exported or otherwise supplied Zotero attachment URLs, which are not automatically publicly reachable—when Page Index cannot fetch one, stop and report that the URL must be made reachable.
- A plain `zotero_file_url` may fail even when the Zotero attachment exists; if the ingest target cannot fetch it directly, do not call that a valid ingest source.
- An authenticated Zotero attachment URL may be fetchable even when the plain Zotero file URL is not. Treat those as different URL classes and verify the actual one being used.
- URL-only Page Index ingest may degrade filenames to generic values such as `file.pdf`. Do not silently accept that degradation when the Zotero attachment filename is available.
- If filename preservation is not supported by the current ingest path, stop and report the limitation clearly instead of treating the ingest as successful.
- Direct public PDF URLs with no Zotero context should use `pageindex-ingest-paper-urls` directly rather than this wrapper.
- Downloading from Zotero to disk or sending PDFs to another OCR provider belongs to `zotero-docai-pipeline`, not this skill.

## Output expectations

When successful, report:
- the Zotero source that was used
- the resolved URL used for ingest
- which URL class was used (`zotero_file_url`, authenticated Zotero attachment URL, or public direct PDF URL)
- the canonical Zotero filename used for ingest
- whether duplicate checking was done
- whether URL fetchability was verified
- whether filename preservation was verified
- the Page Index ingest result for each URL

When blocked, report:
- which Zotero source was missing or unusable
- whether the URL failed because it was non-fetchable, insufficiently authenticated, or not suitable for Page Index URL ingest
- which file could not preserve its canonical filename
- whether the blocker was a missing export/manifest, a likely duplicate, an unreachable URL, or an ingest-path filename limitation
