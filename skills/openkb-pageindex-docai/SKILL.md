---
name: openkb-pageindex-docai
description: Use when ingesting, rebuilding, inspecting, querying, comparing, or exporting documents through a private OpenKB/PageIndex DocAI workflow that needs native OpenKB/PageIndex commands, source-pack provenance, mandatory native+OCR dual extraction, image-retention policy, document versioning, rebuild checks, or public-output/export guardrails.
---

# OpenKB PageIndex DocAI

## Purpose

Use this skill as the source-neutral orchestration layer around native OpenKB and PageIndex. OpenKB/PageIndex remains the authority for active indexed documents; source packs are the provenance, rebuild, comparison, and export-control layer.

## Operating Rules

- Prefer native OpenKB/PageIndex commands for active KB state: `openkb status`, `openkb list`, `openkb add`, `openkb query`, and `openkb remove`.
- Do not create a competing active-document registry. Enrich native state with source-pack metadata only.
- Keep provider credentials in the private runtime environment or native OpenKB `.env` locations. Never write API keys into source packs, public config, reports, or skill files.
- Treat OpenKB compile/query/PageIndex LLM model and OCR model as separate concerns. OCR belongs to the adapter/source-pack layer.
- Before relying on native behavior, verify the installed runtime when practical: package versions, config, command help, and whether installed files match package records.

## Ingest Workflow

1. Identify the source type and durable recovery path: local file, upload, URL, Zotero, GCS, migration, or manual.
2. Create or update a source pack with source hash, source version, sensitivity, recovery metadata, and intended image policy.
3. Run both extraction routes:
   - native extraction using OpenKB/PageIndex-compatible parsing;
   - OCR extraction using the configured OCR adapter.
4. Normalize both outputs into page-aware blocks before comparison.
5. Compare evidence and choose `native`, `ocr`, or `merged`.
6. Write selected content to the native OpenKB/PageIndex input path:
   - PDF when native PDF/PageIndex is best;
   - page-preserving Markdown when OCR or merged reconstruction is best.
7. Run native OpenKB/PageIndex indexing or compilation.
8. Record document family, source version/hash, extraction version, selected reconstruction, conflicts, and active OpenKB document identity.

Never skip dual extraction for cost or speed. Quality is the default priority.

## Comparator

Compare deterministic evidence first:

- page coverage and page-boundary alignment;
- empty-page rate, missing text, repeated text, mojibake, and script/language quality;
- reading order, columns, headings, footnotes, forms, and key-value layout;
- table row/column preservation and numeric/date/currency/identifier fidelity;
- images, figures, charts, captions, coordinates, and retained assets;
- domain-critical facts and contradictions between routes.

Use an LLM judge only as an evidence reviewer over the two extracted outputs plus metrics. It must not invent content.

Merge at page/block level. Every selected block must preserve provenance: `native`, `ocr`, or `both`. Record unresolved numeric/date/identity conflicts in `conflicts.json`; high-stakes conflicts should trigger `needs_human_review`.

If both routes fail minimum fidelity checks, fail ingest rather than indexing a bad reconstruction.

## Image Policy

Supported policies:

- `keep`: store all extracted image bytes under source-pack assets. If any image cannot be stored, fail and inform the user.
- `metadata-only`: keep coordinates, page references, captions, and dimensions, but drop image bytes.
- `drop`: omit image bytes and image metadata unless needed for minimal provenance.

Do not use an `auto` image mode. It hides an important decision.

Avoid duplicated base64 blobs once image files have been written.

## Rebuild Tests

Use rebuild tests before treating the pipeline as durable:

- `source-pack-only`: rebuild a scratch KB from selected Markdown/assets and verify document count, names, summaries, concepts, and representative queries.
- `native-pdf`: rebuild from retained PDFs and verify page count, PageIndex structure, page-content retrieval, and representative queries.
- `zotero-recovery`: recover the PDF from Zotero metadata, verify hash or explicit source-version match, then rebuild.
- `versioning`: verify same filename plus different bytes creates a new source version; same source plus new OCR/merge creates a new extraction version.
- `export-guardrail`: verify public exports are blocked or redacted by default, while private targets can retain complete packs.

## Export Guardrails

Private OpenKB/source-pack content should remain complete and uncensored. Guardrails apply when data leaves the private boundary.

- Classify the target as private or public/shared before export.
- Use guarded modes for public/shared targets: `redacted`, `metadata-only`, or `summary-only`.
- Treat `private-full` as allowed only for private repos/storage unless there is an explicit logged override.
- Fail closed when the target appears public or unknown.
- Scan export bundles for raw provider JSON, OCR text, images, PDFs, secrets, and source packs before release.
- Write an export manifest with mode, target, source documents, sensitivity, redaction status, and override reason when applicable.

## Retention Defaults

- OpenKB `raw/` is active input and should not be casually deleted.
- Native PDF/PageIndex mode keeps PDFs by default for rebuild, audit, figure recovery, and native maintenance.
- OCR-to-Markdown admin documents may drop local original PDFs after verification if OCR JSON, Markdown, assets, manifest, provenance, and OpenKB raw Markdown remain.
- Zotero-backed PDFs may rely on Zotero Cloud/library as canonical storage when recovery metadata is strong.

## Skill Boundaries

- This skill is source-neutral. Do not include Zotero-specific discovery or tag logic here; use a Zotero orchestration skill for that.
- Do not patch OpenKB/PageIndex installed package code unless the user explicitly asks. Prefer wrappers, source packs, and native configuration.
