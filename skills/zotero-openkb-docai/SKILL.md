---
name: zotero-openkb-docai
description: "Zotero attachment orchestration for OpenKB/PageIndex DocAI ingest, recovery, reconciliation, source-pack provenance, backfill, and batch audit."
---

# Zotero OpenKB DocAI

## Purpose

Use this skill for Zotero-specific orchestration on top of the source-neutral OpenKB/PageIndex DocAI workflow. Zotero is the discovery, identity, and recovery layer; OpenKB/PageIndex remains the active KB/indexing layer.

## Relationship To Other Workflows

- Use the existing `zotero-docai-pipeline` repository for Zotero-specific mechanics when available.
- Use the source-neutral `openkb-pageindex-docai` workflow for source packs, dual extraction, comparison, selected reconstruction, rebuild tests, and export guardrails.
- Do not duplicate OpenKB/PageIndex active-document state in a Zotero registry. Store only verified mappings and recovery metadata.

## Zotero Intake Workflow

1. Find candidate Zotero items or attachments, usually through a `docai` tag, collection, explicit item key, or user-provided attachment.
2. Verify attachment identity before ingest:
   - Zotero library type and library ID;
   - item key and attachment key;
   - canonical filename;
   - content hash when the file is available;
   - file size and modified time when useful;
   - DOI/ISBN/title/year metadata when available.
3. Reject ambiguous candidates rather than guessing.
4. Retrieve or locate the PDF only when needed for extraction, backfill, rebuild, or verification.
5. Pass the verified file and Zotero metadata into the source-neutral OpenKB/PageIndex DocAI ingest workflow.
6. Record the OpenKB/PageIndex document identity and selected source-pack path after successful indexing.

## Recovery Policy

Zotero Cloud/library can be treated as canonical PDF storage when recovery metadata is strong. Avoid long-term VPS duplication for large Zotero PDFs unless the user requests local retention or the file cannot be reliably recovered.

Keep enough metadata to recover later:

- library and item identifiers;
- attachment key;
- canonical filename;
- source hash or explicit source-version note;
- Zotero file URL/path when available;
- date/time of verification;
- selected OpenKB/PageIndex document identity.

If a later recovery produces different bytes, treat it as a new source version unless the difference is explicitly expected and documented.

## Handoff Manifest

Use JSONL handoff manifests for read-only Zotero-to-OpenKB coordination when the Zotero pipeline exposes attachments for later OpenKB recovery.

The manifest should contain recovery metadata only:

- library, item, and attachment identifiers;
- canonical filename;
- safe unauthenticated file endpoint or local path when available;
- paper metadata and OpenKB policy hints.

Do not include PDF bytes, authenticated URLs, query-string tokens, API keys, or signed download links.

Prefer dry-run/export-only manifest generation and validation before PDF recovery or indexing. Verify row count, canonical filenames, absence of secrets and PDF bytes, and enough Zotero identity to redownload the attachment later.

## Batch Rules

- Batch candidates may be discovered in Zotero, but each attachment must still pass identity verification before ingest.
- Do not ingest degraded, generic, auto-suffixed, or ambiguous attachment matches.
- Use resumable manifests or JSONL logs for batch progress when available.
- Fail individual ambiguous items and continue only when the batch can safely isolate failures.

## Backfill And Rebuild

Use Zotero recovery for missing local PDFs when backfilling old OpenKB/PageIndex entries into the dual-extraction source-pack format.

For each backfill:

1. Recover the original attachment from Zotero or the Mac node.
2. Verify it against known filename/hash/provenance.
3. Run the source-neutral mandatory dual extraction.
4. Compare, select or merge, and rebuild a scratch KB or update the active KB as appropriate.
5. Preserve the prior active document identity as historical provenance.

## Guardrails

- Do not export private Zotero PDFs, OCR text, source packs, or provider JSON to public targets without explicit override.
- Private repos and private storage are acceptable for complete source packs.
- Public outputs should default to redacted, metadata-only, or summary-only modes.
- Never store Zotero credentials or provider API keys in source packs or skill files.

## Skill Boundaries

- This skill does not replace Zotero, OpenKB, PageIndex, or the existing Zotero pipeline repository.
- It coordinates them and preserves verified identity/provenance.
- If an existing skill needs modification, ask the user for explicit confirmation first.
