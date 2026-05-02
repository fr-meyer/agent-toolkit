---
name: pageindex-ingest-paper-urls
description: Use this skill when the user needs to ingest one or more direct public PDF URLs into Page Index, especially when they ask to submit papers, add PDFs to Page Index, or process URLs after checking for duplicates. Apply it when requests involve public PDF URLs, Page Index submission, or URL-based ingestion workflows with no Zotero context. Do not use it for paper finding alone, reading existing Page Index papers, summarization, Zotero attachment exports or manifests, local file paths, or non-Page-Index upload workflows.
---

# Page Index Ingest Paper URLs

## Goal

Ingest public PDF URLs into Page Index with a conservative duplicate check first, saving processed documents into the intended Page Index folder when a target folder is selected.

## When to use

Use this skill when the user already has one or more **direct public PDF URLs** and wants them added to Page Index.

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
2. If the user, manifest, or calling workflow specifies a target Page Index folder, resolve it to a PageIndex `folder_id` before duplicate checking or ingest.
   - Use `pageindex__list_folders` when only a folder name is supplied.
   - If multiple folders could match, ask the user to choose instead of guessing.
   - If no folder is specified, use the default PageIndex destination behavior.
3. Run `pageindex-find-papers` first when there is any useful filename/title/citation hint, and treat likely matches conservatively.
4. Always perform a global exact-name duplicate check before any folder-targeted upload, even when the user selected a specific destination folder. This catches PageIndex's global document-name uniqueness behavior before it creates an auto-suffixed duplicate.
5. When a target folder is selected, also duplicate-check and verify results within that same folder whenever the available PageIndex tool supports a `folder_id` parameter.
6. Also check for an exact-name duplicate outside the selected folder before upload when possible; PageIndex may enforce global document-name uniqueness and auto-suffix duplicates such as `_1.pdf`, which is not an exact filename-preserving success.
7. If a verified duplicate exists in the selected destination scope, stop and report the match instead of ingesting again.
8. If the exact filename exists outside the selected destination scope, stop and report the folder-placement blocker instead of uploading a suffixed duplicate; ask whether to keep the existing document, delete/recreate, or choose another remediation.
9. If no verified duplicate or global-name blocker is found, submit the public PDF URL with `pageindex__process_document`, passing `folder_id` so the uploaded/processed document is saved in the selected PageIndex folder.
10. After ingest, verify the resulting document in the same folder when folder-scoped verification is available.
11. Report the resulting Page Index document status or any ingestion failure clearly.

## Gotchas

- This skill is URL-only. Do not accept local file paths here.
- Do not assume a URL is public just because it looks like a PDF link.
- PageIndex upload folder selection is done through `folder_id`, not folder display name. Resolve names before upload.
- Do not silently upload into the root/default destination if the user selected a folder but folder resolution failed; stop and ask or report the blocker.
- Do not treat PageIndex auto-suffixed names such as `_1.pdf` as success; they indicate exact filename preservation failed, often because an exact-name duplicate already exists elsewhere.
- Never rely only on folder-scoped duplicate checks before folder upload; do the global exact-name check too.
- If the user only has a filename, citation, or title, resolve that first with `pageindex-find-papers` before ingesting anything.
- If the user needs Zotero attachments, Zotero attachment manifests, or `zotero_file_url` sources, use `zotero-docai-ingest-to-pageindex` instead.

## Output expectations

When the ingest succeeds, return:
- the URL ingested
- the Page Index document identifier or result summary
- whether duplicate checking was performed
- the target PageIndex folder name/id, if one was selected

When the ingest is blocked, return:
- the reason
- the likely duplicate, unresolved folder, or missing input that caused the block
