---
name: zotero-docai-ingest-to-pageindex
description: Use this skill when the user needs to turn Zotero-derived PDF sources into Page Index ingests or reconcile Zotero-to-PageIndex bridge rows, especially from zotero_file_url exports, Zotero attachment manifests, Zotero item selections, or zotero-docai-pipeline discovery outputs. Apply it when requests involve Zotero-backed batches of PDFs that should end up in Page Index, verified already-existing Zotero/PageIndex mappings, or missing bridge rows for already-uploaded Zotero items, even if the user does not mention Page Index skill names. Do not use it for direct public PDF URLs with no Zotero context, direct Zotero PDF download, Page Index reading or summarization, local PDF paths without exported URLs, or Page Index ingestion that is already URL-only and does not involve Zotero.
---

# Zotero DocAI Ingest to Page Index

## Goal

Bridge Zotero-derived PDF sources into Page Index using a Zotero-derived URL ingest workflow while preserving the Zotero attachment filename as the canonical ingest filename, and maintain a durable Zotero↔PageIndex bridge for verified mappings.

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
- reconciling or backfilling Zotero↔PageIndex bridge rows for Zotero items that are already uploaded or processed in PageIndex

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
- Add the PageIndex-success tag only after PageIndex-side verification confirms an exact canonical-filename match, whether the document was newly uploaded, already existed in PageIndex, or was recovered through bridge backfill.
- Maintain the durable Zotero↔PageIndex bridge table/manifest as an explicit post-verification artifact. Upsert or refresh a bridge row whenever PageIndex exact-canonical-filename verification succeeds, including newly uploaded documents, exact duplicate-existing documents, and Zotero items that were already uploaded/processed before this run but have no bridge row yet.
- Treat bridge reuse as a maintenance operation, not a blind cache hit: before reusing an existing row, re-check Zotero attachment identity/filename and PageIndex document identity/status/folder against live state whenever the relevant tools/data are available. If Zotero or PageIndex no longer matches the row, update the row's maintenance metadata and either refresh the mapping after exact verification or mark/report it as stale/blocked; never reuse mismatched bridge data silently.
- Treat missing bridge rows for previously uploaded/processed Zotero items as a reconciliation/backfill task: verify the exact PageIndex document first, then create the bridge row; do not require a fresh upload when an exact verified PageIndex document already exists.
- A bridge row should include, when available: Zotero item key, Zotero attachment key, citation key, item title, DOI, canonical Zotero filename, PageIndex document name, PageIndex document id, PageIndex folder id/name or destination scope, verification status (`uploaded_verified`, `existing_verified`, `backfilled_verified`, or `refreshed_verified`), verification timestamp, and concise match evidence.
- Do not create or refresh bridge rows for ambiguous matches, inaccessible/still-processing PageIndex documents, generic/degraded filenames, folder-placement/global-name conflicts, or any case where the PageIndex document identity is not exact and verified.
- If a durable bridge table/manifest is configured or discoverable, bridge upsert/refresh should happen before Zotero success writeback and before queue-tag removal. If no durable bridge destination is available, record the bridge fields in the run manifest/report and report the missing bridge destination as a blocker for full reconciliation instead of silently skipping it.
- Add the failure tag when fetchability, upload, processing, duplicate verification, exact filename preservation, or required bridge reconciliation fails; do not mark a degraded, partially verified, or unbridgeable ingest as PageIndex-success.
- When a target PageIndex folder is selected/configured, resolve it to `folder_id`, pass that `folder_id` to PageIndex MCP submission, and verify the document in that same folder before writeback.
- Before uploading into a target folder, always check whether the exact canonical filename already exists globally in PageIndex, not only inside the selected folder. If it exists elsewhere, stop and report the folder-placement/global-name blocker instead of creating an auto-suffixed duplicate such as `_1.pdf`; when Zotero writeback is enabled, add `docai-error` and include where the existing PageIndex document is already present.
- Do not assume that a plain `zotero_file_url` is directly fetchable by Page Index.
- Distinguish clearly between:
  - a plain Zotero file URL
  - an authenticated Zotero attachment URL
  - a publicly reachable direct PDF URL

## Required workflow

1. Confirm the user is working from Zotero-derived PDF source URLs, a `zotero-docai-pipeline` export/manifest, or a Zotero item selection intended for bridge reconciliation/backfill.
2. If the user only has paper metadata such as title, filename, or citation, run `pageindex-find-papers` first to check whether the paper already exists in Page Index.
3. If a target PageIndex folder is specified by the user, config, or manifest, resolve it to a PageIndex `folder_id`; if only a display name is provided, use PageIndex folder listing to resolve it and stop for clarification on ambiguous matches.
4. Extract the Zotero attachment filename and treat it as the canonical ingest filename.
5. Check the durable Zotero↔PageIndex bridge table/manifest, if configured or discoverable, for an existing row keyed by Zotero item key, Zotero attachment key, and/or canonical filename.
6. If a bridge row exists, run bridge maintenance before reuse: verify the live Zotero attachment identity/filename and the referenced PageIndex document id/name/status/folder. If everything still matches, refresh `last_verified_at`/evidence as needed and treat the record as verified without uploading; if any live state mismatches, do not reuse the row until it is refreshed by exact verification or marked/report as stale/blocked.
7. If the bridge row is missing, stale, or mismatched for a Zotero item that appears already uploaded/processed, search PageIndex for an exact canonical-filename match in the intended scope; when verified, upsert a `backfilled_verified` or `refreshed_verified` bridge row and skip upload.
8. Normalize the Zotero source into the actual ingestable URL form when upload is still needed:
   - use a plain `zotero_file_url` only if it is truly fetchable by the ingest target
   - use an authenticated Zotero attachment URL when the plain Zotero file URL is not fetchable and authenticated access is the intended bridge
   - do not treat a non-fetchable Zotero URL as ingestion-ready
9. Verify that the chosen URL is fetchable by the selected ingest path before calling the Page Index submission step.
10. Verify that the selected ingest method can retain the canonical Zotero filename in Page Index.
11. Hand the resulting URL to `pageindex-ingest-paper-urls` for the actual Page Index submission step only if all conditions hold:
   - no valid bridge row or exact existing PageIndex document already resolved the record
   - the URL is fetchable
   - filename preservation remains intact
   - the selected PageIndex folder, if any, has been resolved to `folder_id`
12. When a target folder was resolved, pass `folder_id` through the PageIndex MCP upload call so the processed document is saved in that folder.
13. Before uploading, always run a global exact-canonical-filename check in addition to any target-folder scoped duplicate check.
14. If an exact canonical-filename document already exists in PageIndex, treat the upload as skipped/duplicate success only after PageIndex-side verification confirms the exact filename match in the intended destination scope, then upsert or refresh the Zotero↔PageIndex bridge row.
15. After submission, verify the resulting PageIndex document name when needed to confirm that filename preservation actually held, and verify it in the selected folder when folder-scoped verification is available.
16. After any newly uploaded document is verified, upsert the Zotero↔PageIndex bridge row with the PageIndex document name/id, destination scope, verification timestamp, and match evidence before success writeback.
17. If the exact canonical filename exists outside the intended target folder and PageIndex cannot place or move that exact document into the selected folder through MCP, treat this as blocked/failure for the target-folder workflow rather than uploading a suffixed duplicate; record and report the existing PageIndex document name/id and folder/location.
18. If Zotero writeback is explicitly enabled and a global exact-name/folder-placement conflict blocks the target-folder upload, add the failure tag (`docai-error` by default), keep the queue tag (`docai` by default), and include the existing PageIndex location in the report/manifest for manual resolution.
19. If Zotero writeback is explicitly enabled and the record is verified as newly uploaded, exact-duplicate-existing, or bridge-backfilled, add the success tag (`docai-pageindex` by default) to the relevant Zotero item/attachment if missing only after the required bridge upsert/refresh succeeds. If bridge maintenance is required but cannot be completed, treat the record as blocked instead of success-tagging it.
20. If Zotero writeback is explicitly enabled and the record fails or is blocked, add the failure tag (`docai-error` by default) to the relevant Zotero item/attachment.
21. Remove the queue tag (`docai` by default) only on verified PageIndex success and only when that behavior is explicitly enabled/configured; keep it on failures so failed records remain retryable/reviewable.
22. Report which URLs were accepted, which were blocked, whether any likely duplicate was already found in PageIndex, whether fetchability was verified, whether filename preservation was verified, which PageIndex folder was targeted, whether bridge rows were created/refreshed/backfilled/skipped, and whether Zotero tag writeback was applied or skipped.


## Bridge maintenance

Treat bridge maintenance as part of every reuse/reconciliation pass, not as a separate optional cleanup.

When an existing bridge row is found:

1. Revalidate Zotero-side state when available:
   - the Zotero item still exists
   - the attachment key still belongs to that item
   - the attachment filename is still the canonical filename and is not generic/degraded
   - relevant Zotero tags are checked if writeback decisions depend on them
2. Revalidate PageIndex-side state through MCP:
   - the referenced document is accessible and completed
   - `pageindex_document_name` exactly equals the current canonical Zotero filename
   - the document id/name/folder match the intended destination scope
   - no global exact-name/folder-placement conflict has appeared
3. If both sides still match, refresh bridge metadata such as `last_verified_at`, `last_checked_at`, `verification_status=refreshed_verified`, evidence paths, PageIndex page count/status, folder id/name, and observed Zotero tag state when useful.
4. If Zotero changed but PageIndex can be matched exactly to the new canonical filename, update the row to the new verified mapping and mark it `refreshed_verified`.
5. If PageIndex changed but another exact canonical-filename document is verified in the intended scope, update the PageIndex id/name/folder fields and mark the row `refreshed_verified`.
6. If either side mismatches and no exact verified replacement is found, update maintenance metadata such as `last_checked_at`, `maintenance_status`, `stale_reason`, and concise evidence in the bridge or run manifest, but do not treat the row as reusable success.
7. Preserve prior evidence when possible (`notes` or `evidence_paths`) so a refreshed row remains auditable.

Important: never overwrite canonical mapping fields with unverified observations. Store observations such as `observed_zotero_filename` or `observed_pageindex_document_name` separately until exact verification succeeds.

Rows that are stale, blocked, ambiguous, inaccessible, generic/degraded, auto-suffixed, still-processing, or folder-conflicted must not be used to add `docai-pageindex` or remove the queue tag. They should be reported as `stale_refreshed`, `stale_blocked`, or `needs_manual_resolution` depending on the outcome.

## Gotchas

- MCP-only is a hard constraint for this workflow. Do not bypass MCP filename or fetchability limits with direct Page Index API/SDK upload code unless Franck explicitly changes the constraint.
- This skill does not invent Zotero URLs; it expects exported or otherwise supplied Zotero attachment URLs, which are not automatically publicly reachable—when Page Index cannot fetch one, stop and report that the URL must be made reachable.
- A plain `zotero_file_url` may fail even when the Zotero attachment exists; if the ingest target cannot fetch it directly, do not call that a valid ingest source.
- An authenticated Zotero attachment URL may be fetchable even when the plain Zotero file URL is not. Treat those as different URL classes and verify the actual one being used.
- URL-only Page Index ingest may degrade filenames to generic values such as `file.pdf`. Do not silently accept that degradation when the Zotero attachment filename is available.
- If filename preservation is not supported by the current ingest path, stop and report the limitation clearly instead of treating the ingest as successful.
- `ZOTERO_WRITE_KEY` or equivalent write credentials are required only for explicit Zotero tag writeback. Do not require write credentials for read-only discovery, duplicate checking, URL fetchability checks, or PageIndex MCP submission.
- Do not add `docai-pageindex` just because PageIndex submission returned success; wait until PageIndex lookup/metadata confirms the exact canonical filename and the required bridge row has been upserted/refreshed or the missing bridge destination has been explicitly reported.
- Existing exact duplicates in PageIndex are successful outcomes for writeback and bridge-backfill purposes, but only if the duplicate name exactly matches the canonical Zotero attachment filename in the intended destination scope.
- Do not treat PageIndex auto-suffixed names such as `_1.pdf` as success; they indicate exact filename preservation failed, often because an exact-name duplicate already exists elsewhere.
- Never rely only on a target-folder scoped duplicate check before uploading; do the global exact-canonical-filename check too.
- Never treat an existing `docai-pageindex` tag as proof that the bridge is complete; if the bridge row is missing or stale, run exact PageIndex verification and backfill it.
- Do not create bridge rows from fuzzy title matches, generic filenames, auto-suffixed filenames, or PageIndex documents that are still processing or inaccessible.
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
- the Zotero↔PageIndex bridge row outcome for each record (`created`, `refreshed`, `backfilled`, `already-current`, `stale-refreshed`, `stale-blocked`, `needs-manual-resolution`, `skipped`, or `blocked`) and the bridge destination/manifest path when available
- any Zotero tags added or intentionally left unchanged, including `docai-pageindex`, `docai-error`, and `docai`

When blocked, report:
- which Zotero source was missing or unusable
- whether the URL failed because it was non-fetchable, insufficiently authenticated, or not suitable for Page Index URL ingest
- which file could not preserve its canonical filename
- whether the blocker was a missing export/manifest, a missing or unavailable bridge destination, a stale/mismatched bridge row, a bridge upsert/refresh failure, a likely duplicate, an unresolved folder, a global-name/folder-placement conflict, an unreachable URL, or an ingest-path filename limitation
- for global-name/folder-placement conflicts, the existing PageIndex document name/id and folder/location where it is already present
- whether bridge backfill/upsert was applied or skipped, and why
- whether `docai-error` writeback was applied or skipped, and why
