---
name: pageindex-ingest-paper-urls
description: Use this skill for PageIndex URL ingestion: submitting public PDF URLs, resolving/creating PageIndex target folders, duplicate-checking before process_document, and explicitly approved temporary HTTPS bridge workflows for local PDFs. Do not use it for reading/summarizing existing documents, Zotero attachment workflows, generic local-file uploads, or non-PageIndex upload targets.
---

# Page Index Ingest Paper URLs

## Goal

Ingest public PDF URLs into Page Index with a conservative duplicate check first, saving processed documents into the intended Page Index folder when a target folder is selected.

## When to use

Use this skill when the user already has one or more **direct public PDF URLs** and wants them added to Page Index.

Use it for:
- URL-based Page Index ingestion
- adding papers after a duplicate check
- creating or resolving PageIndex folder destinations needed for URL ingestion
- workflows that will later feed Page Index reading or summarization skills

Do not use it for:
- finding papers already in Page Index
- reading or summarizing papers already in Page Index
- Zotero attachment exports, Zotero manifests, or zotero_file_url sources
- local PDF paths unless the user explicitly approves a temporary HTTPS bridge that converts them into direct PDF URLs for MCP-only ingestion
- attachment bytes or filesystem uploads
- non-Page-Index upload targets

## Required workflow

1. For each URL, inspect the source filename or any user-provided paper metadata.
2. If the user, manifest, or calling workflow specifies a target Page Index folder, resolve it to a PageIndex `folder_id` before duplicate checking or ingest.
   - Use `pageindex__list_folders` when only a folder name is supplied.
   - If multiple folders could match, ask the user to choose instead of guessing.
   - If no folder is specified, use the default PageIndex destination behavior.
   - `process_document` accepts a `folder_id`, not a folder path. Do not assume that passing a path-like value will create folders automatically.
   - If a required folder is missing and the user has approved folder creation, create the folder via PageIndex MCP before ingest, then verify it with `pageindex__list_folders`.
   - Prefer a first-class `create_folder` tool if OpenClaw exposes one. If it is not exposed, see **Hidden PageIndex `create_folder` MCP quirk** below.
3. Run `pageindex-find-papers` first when there is any useful filename/title/citation hint, and treat likely matches conservatively.
4. Always perform a global exact-name duplicate check before any folder-targeted upload, even when the user selected a specific destination folder. This catches PageIndex's global document-name uniqueness behavior before it creates an auto-suffixed duplicate.
5. When a target folder is selected, also duplicate-check and verify results within that same folder whenever the available PageIndex tool supports a `folder_id` parameter.
6. Also check for an exact-name duplicate outside the selected folder before upload when possible; PageIndex may enforce global document-name uniqueness and auto-suffix duplicates such as `_1.pdf`, which is not an exact filename-preserving success.
7. If a verified duplicate exists in the selected destination scope, stop and report the match instead of ingesting again.
8. If the exact filename exists outside the selected destination scope, stop and report the folder-placement blocker instead of uploading a suffixed duplicate; ask whether to keep the existing document, delete/recreate, or choose another remediation.
9. If no verified duplicate or global-name blocker is found, submit the public PDF URL with `pageindex__process_document`, passing `folder_id` so the uploaded/processed document is saved in the selected PageIndex folder.
10. After ingest, verify the resulting document in the same folder when folder-scoped verification is available.
11. Report the resulting Page Index document status or any ingestion failure clearly.

## Hidden PageIndex `create_folder` MCP quirk

As of 2026-05-17, PageIndex Chat MCP may accept `create_folder` even when it is missing from `tools/list`, which means OpenClaw may not expose it as a normal tool.

Use this fallback only for non-destructive folder creation after the user has approved the folder change:

1. Prefer a first-class `create_folder` tool if one is exposed.
2. If not exposed, make a harmless raw MCP validation probe. An empty `create_folder` call should fail with input validation requiring `name`; an unknown-tool error means the fallback is unavailable.
3. Create one path segment at a time with raw MCP `tools/call`:

```json
{
  "name": "target-folder-name",
  "parent_folder_id": "existing-parent-folder-id"
}
```

4. Verify each new folder with `pageindex__list_folders(parent_folder_id=...)` and use the returned folder ID for uploads.

Do not use raw MCP for unadvertised destructive tools. Do not switch to PageIndex API/SDK/HTTP multipart/API-key uploads unless the user explicitly overrides the MCP-only requirement. Do not permanently store OAuth tokens or raw MCP credentials.

## Temporary HTTPS bridge exception for local PDFs

This skill is URL-only by default. For local PDFs, use a temporary HTTPS bridge only when the user explicitly approves temporary public exposure for MCP-only ingestion.

Required safeguards:

- Run duplicate checks and resolve/create target folders before opening the bridge when possible.
- Prefer a short-lived tunnel/bridge over persistent sharing services such as Google Drive for sensitive documents.
- Use unguessable random URL tokens; do not put real filenames in URL paths.
- Serve PDFs with `Content-Type: application/pdf` and exact intended filenames via `Content-Disposition` so PageIndex preserves canonical names.
- Add `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow, noarchive`.
- Call `pageindex__process_document` with the bridge URL and final `folder_id`.
- Do not store or report transient bridge URLs or tokens.
- Shut down the bridge immediately after successful submissions; verification can happen after shutdown.
- Remove temporary manifests/logs/scripts that contain tokens or URLs.

If the user has not approved temporary exposure, stop and explain the privacy tradeoff instead of creating a bridge.

## Gotchas

- This skill is URL-only by default. Do not accept local file paths unless the user explicitly approved the temporary HTTPS bridge workflow above.
- Do not assume a URL is public just because it looks like a PDF link.
- PageIndex upload folder selection is done through `folder_id`, not folder display name. Resolve names before upload.
- PageIndex MCP `process_document` does not create nested folders from path strings. Resolve or create folders first, then pass the final `folder_id`.
- Do not silently upload into the root/default destination if the user selected a folder but folder resolution failed; stop and ask or report the blocker.
- Do not treat PageIndex auto-suffixed names such as `_1.pdf` as success; they indicate exact filename preservation failed, often because an exact-name duplicate already exists elsewhere.
- Never rely only on folder-scoped duplicate checks before folder upload; do the global exact-name check too.
- If the user only has a filename, citation, or title, resolve that first with `pageindex-find-papers` before ingesting anything.
- If the user needs Zotero attachments, Zotero attachment manifests, or `zotero_file_url` sources, use `zotero-docai-ingest-to-pageindex` instead.

## Output expectations

When the ingest succeeds, return:
- the URL ingested, or a redacted statement for transient bridge URLs
- the Page Index document identifier or result summary
- whether duplicate checking was performed
- the target PageIndex folder name/id, if one was selected

When the ingest is blocked, return:
- the reason
- the likely duplicate, unresolved folder, or missing input that caused the block
