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
- Treat Zotero tag writeback as an explicit post-verification step, not as part of discovery or upload by default.
- When Zotero tag writeback is enabled, use `docai-pageindex` as the default PageIndex-success tag and `docai-error` as the default failure tag unless the user/config explicitly supplies different tag names.
- Add the PageIndex-success tag only after PageIndex-side verification confirms an exact canonical-filename match, whether the document was newly uploaded or already existed in PageIndex.
- Add the failure tag when fetchability, upload, processing, duplicate verification, or exact filename preservation fails; do not mark a degraded or partially verified ingest as PageIndex-success.
- When a target PageIndex folder is selected/configured, resolve it to `folder_id`, pass that `folder_id` to PageIndex MCP submission, and verify the document in that same folder before writeback.
- Before uploading into a target folder, always check whether the exact canonical filename already exists globally in PageIndex, not only inside the selected folder. If it exists elsewhere, stop and report the folder-placement/global-name blocker instead of creating an auto-suffixed duplicate such as `_1.pdf`; when Zotero writeback is enabled, add `docai-error` and include where the existing PageIndex document is already present.
- Do not assume that a plain `zotero_file_url` is directly fetchable by Page Index.
- Distinguish clearly between:
  - a plain Zotero file URL
  - an authenticated Zotero attachment URL
  - a publicly reachable direct PDF URL

## Required workflow

1. Confirm the user is working from Zotero-derived PDF source URLs or a `zotero-docai-pipeline` export/manifest.
2. If the user only has paper metadata such as title, filename, or citation, run `pageindex-find-papers` first to check whether the paper already exists in Page Index.
3. If a target PageIndex folder is specified by the user, config, or manifest, resolve it to a PageIndex `folder_id`; if only a display name is provided, use PageIndex folder listing to resolve it and stop for clarification on ambiguous matches.
4. Extract the Zotero attachment filename and treat it as the canonical ingest filename.
5. Normalize the Zotero source into the actual ingestable URL form:
   - use a plain `zotero_file_url` only if it is truly fetchable by the ingest target
   - use an authenticated Zotero attachment URL when the plain Zotero file URL is not fetchable and authenticated access is the intended bridge
   - do not treat a non-fetchable Zotero URL as ingestion-ready
6. Verify that the chosen URL is fetchable by the selected ingest path before calling the Page Index submission step.
7. Verify that the selected ingest method can retain the canonical Zotero filename in Page Index.
8. Hand the resulting URL to `pageindex-ingest-paper-urls` for the actual Page Index submission step only if both conditions hold:
   - the URL is fetchable
   - filename preservation remains intact
   - the selected PageIndex folder, if any, has been resolved to `folder_id`
9. When a target folder was resolved, pass `folder_id` through the PageIndex MCP upload call so the processed document is saved in that folder.
10. Before uploading, always run a global exact-canonical-filename check in addition to any target-folder scoped duplicate check.
11. After submission, verify the resulting Page Index document name when needed to confirm that filename preservation actually held, and verify it in the selected folder when folder-scoped verification is available.
12. If an exact canonical-filename document already exists in Page Index, treat the upload as skipped/duplicate success only after PageIndex-side verification confirms the exact filename match in the intended destination scope.
13. If the exact canonical filename exists outside the intended target folder and PageIndex cannot place or move that exact document into the selected folder through MCP, treat this as blocked/failure for the target-folder workflow rather than uploading a suffixed duplicate; record and report the existing PageIndex document name/id and folder/location.
14. If Zotero writeback is explicitly enabled and a global exact-name/folder-placement conflict blocks the target-folder upload, add the failure tag (`docai-error` by default), keep the queue tag (`docai` by default), and include the existing PageIndex location in the report/manifest for manual resolution.
15. If Zotero writeback is explicitly enabled and the record is verified as newly uploaded or exact-duplicate-existing, add the success tag (`docai-pageindex` by default) to the relevant Zotero item/attachment if missing.
16. If Zotero writeback is explicitly enabled and the record fails or is blocked, add the failure tag (`docai-error` by default) to the relevant Zotero item/attachment.
17. Remove the queue tag (`docai` by default) only on verified PageIndex success and only when that behavior is explicitly enabled/configured; keep it on failures so failed records remain retryable/reviewable.
18. Report which URLs were accepted, which were blocked, whether any likely duplicate was already found in Page Index, whether fetchability was verified, whether filename preservation was verified, which PageIndex folder was targeted, and whether Zotero tag writeback was applied or skipped.

## Gotchas

- MCP-only is a hard constraint for this workflow. Do not bypass MCP filename or fetchability limits with direct Page Index API/SDK upload code unless Franck explicitly changes the constraint.
- This skill does not invent Zotero URLs; it expects exported or otherwise supplied Zotero attachment URLs, which are not automatically publicly reachable—when Page Index cannot fetch one, stop and report that the URL must be made reachable.
- A plain `zotero_file_url` may fail even when the Zotero attachment exists; if the ingest target cannot fetch it directly, do not call that a valid ingest source.
- An authenticated Zotero attachment URL may be fetchable even when the plain Zotero file URL is not. Treat those as different URL classes and verify the actual one being used.
- URL-only Page Index ingest may degrade filenames to generic values such as `file.pdf`. Do not silently accept that degradation when the Zotero attachment filename is available.
- If filename preservation is not supported by the current ingest path, stop and report the limitation clearly instead of treating the ingest as successful.
- `ZOTERO_WRITE_KEY` or equivalent write credentials are required only for explicit Zotero tag writeback. Do not require write credentials for read-only discovery, duplicate checking, URL fetchability checks, or PageIndex MCP submission.
- Do not add `docai-pageindex` just because PageIndex submission returned success; wait until PageIndex lookup/metadata confirms the exact canonical filename.
- Existing exact duplicates in PageIndex are successful outcomes for writeback purposes, but only if the duplicate name exactly matches the canonical Zotero attachment filename in the intended destination scope.
- Do not treat PageIndex auto-suffixed names such as `_1.pdf` as success; they indicate exact filename preservation failed, often because an exact-name duplicate already exists elsewhere.
- Never rely only on a target-folder scoped duplicate check before uploading; do the global exact-canonical-filename check too.
- Do not silently upload into the PageIndex root/default destination when the workflow selected a specific folder but folder resolution failed.
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
- the target PageIndex folder name/id, if one was selected
- whether Zotero writeback was enabled
- any Zotero tags added or intentionally left unchanged, including `docai-pageindex`, `docai-error`, and `docai`

When blocked, report:
- which Zotero source was missing or unusable
- whether the URL failed because it was non-fetchable, insufficiently authenticated, or not suitable for Page Index URL ingest
- which file could not preserve its canonical filename
- whether the blocker was a missing export/manifest, a likely duplicate, an unresolved folder, a global-name/folder-placement conflict, an unreachable URL, or an ingest-path filename limitation
- for global-name/folder-placement conflicts, the existing PageIndex document name/id and folder/location where it is already present
- whether `docai-error` writeback was applied or skipped, and why
