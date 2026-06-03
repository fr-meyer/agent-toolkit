---
name: document-renaming
description: Use this skill when organizing, renaming, or preparing local/user document files before import, archiving, OCR, OpenKB/PageIndex ingest, tax/admin processing, or folder cleanup. It enforces reading or OCRing file contents before naming, dry-run rename plans, date-first portable names, collision-safe moves, hash verification, and durable rename manifests.
---

# Document Renaming

## Goal

Rename and organize user documents only after understanding what each file is. A filename is metadata; do not invent it from a folder name or vague original filename when the content is unread.

Use this before imports, archives, source-pack creation, OpenKB/PageIndex ingest, financial/admin workflows, or any cleanup where the human will later rely on local filenames.

## Operating Rules

- Inspect the folder before moving anything. List files, extensions, sizes, dates, and existing subfolders.
- Read each document before assigning a canonical name. Use embedded text first; use OCR when text is missing, scanned, garbled, or not enough to identify the file.
- Prefer exact evidence from the document: document date, issuer, person/entity, account/project, document type, amount/reference number, and status.
- Never rename from only the current filename unless the document content has already been verified in this same workflow or by a matching hash in a trusted manifest.
- Dry-run first. Show or save the proposed source path, target path, reason/evidence, and collision status before applying moves.
- Refuse ambiguous cases. If two plausible names exist, if issuer/date/person/type is unclear, or if files appear duplicated with different bytes, keep the original name and mark `needs-review`.
- Apply only collision-safe moves. Do not overwrite. If the target exists, compare hashes and stop for human review unless it is an exact duplicate and the user approved deduplication.
- Verify after moving. Re-list final paths and recompute hashes to prove bytes did not change.
- Write a manifest for any non-trivial rename/organization pass.

## Naming Pattern

Default to ASCII-safe, date-first names:

```text
YYYY-MM-DD_issuer_subject_context_document-type.ext
```

Use lowercase, digits, hyphens inside terms, and underscores between fields. Keep names portable across macOS, Linux, Windows, cloud storage, git, and shell scripts:

- no spaces;
- no slashes, colons, quotes, shell metacharacters, or emoji;
- avoid accents and non-Latin characters unless the user explicitly wants local-language filenames;
- keep the extension unchanged and lowercase when practical.

Examples:

```text
2026-03-14_bank-person_fixed-deposit_maturity-closure-confirmation.pdf
2025-12-31_broker-person_financial-income_withholding-statement.pdf
2026-05-30_university-person_tax-statement_income-summary.pdf
```

For related batches, create a date-first folder:

```text
YYYY-MM-DD_issuer_context_subject/
```

Example:

```text
2026-03-14_bank_fixed-deposit_maturity_person/
```

## Field Guidance

Use only fields that help future retrieval. Omit fields you cannot verify.

- `YYYY-MM-DD`: document date, transaction date, statement period end, or event date. If only month is known, use `YYYY-MM`; if no reliable date exists, put the file in `needs-review` instead of inventing one.
- `issuer`: institution, sender, agency, company, bank, university, court, or source system.
- `subject`: person, entity, property, account nickname, project, or collection owner. Keep private names only when appropriate for the target folder.
- `context`: product, account class, tax year, application, case, booking, or document family.
- `document-type`: what the file is, not what it is about: `invoice`, `receipt`, `statement`, `withholding-statement`, `maturity-closure-confirmation`, `termination-estimate`, `contract`, `notice`, `certificate`, `report`.

If an official document title is clearer than a generic type, normalize it into a short English slug while preserving enough meaning.

## Workflow

### 1. Inventory

List candidate files and compute hashes before renaming:

```bash
find <folder> -maxdepth 2 -type f -print
find <folder> -maxdepth 2 -type f -print0 | xargs -0 shasum -a 256
```

Use the platform's native hash command when needed (`shasum`, `sha256sum`, `Get-FileHash`).

### 2. Read and classify

For each file, capture:

- original path;
- SHA-256;
- page count or basic file metadata when available;
- extraction method: native text, OCR, prior trusted manifest, or manual review;
- evidence for date, issuer, subject, context, and document type;
- proposed canonical filename or `needs-review`.

For PDFs and scans, read enough pages to identify the document and verify critical values. For admin/financial/legal/medical documents, read all pages unless clearly irrelevant boilerplate.

### 3. Plan

Create a dry-run plan with one row per file:

```text
status | sha256 | original_path | proposed_path | evidence | notes
```

Statuses:

- `move`: clear evidence and target does not exist;
- `already-ok`: current path/name already matches the rule;
- `needs-review`: ambiguous, unreadable, conflicting, or too sensitive;
- `duplicate-review`: same or similar content requires human deduplication decision;
- `refuse`: target collision, unsafe path, missing hash, or other hard stop.

Do not proceed if any planned `move` would leave related documents split incoherently across folders.

### 4. Apply

Apply only the accepted `move` rows. Use commands that preserve bytes and fail on collisions. Create destination folders explicitly. Do not use broad glob moves unless every matched file has already been mapped by hash.

### 5. Verify

After moving:

- re-list the folder tree;
- recompute hashes at final paths;
- confirm every moved file hash equals its pre-move hash;
- confirm no unexpected source files remain at the old level;
- write or update the rename manifest.

## Manifest

For any folder cleanup, save a Markdown or JSONL manifest near the project memory/report location or in the destination folder when appropriate.

Minimum Markdown manifest:

```markdown
# Rename Manifest - <date> - <folder/project>

Source folder: `<absolute path>`

## Method

- How files were read/OCRed
- Hash verification method
- Dry-run/collision policy

## Files

| SHA-256 | Original path | Final path | Evidence | Status |
| --- | --- | --- | --- | --- |
```

For imports, the rename manifest should be written before or alongside the import manifest so the source-folder organization remains auditable.

## OpenKB/PageIndex Import Rule

When the user gives a local/admin folder to import:

1. inventory the original folder;
2. read/OCR and classify documents;
3. rename/organize the original folder or get explicit approval to leave originals untouched;
4. create a rename manifest;
5. then stage/import into OpenKB/PageIndex.

If import has already happened and the original folder was not cleaned up, correct the original folder afterward using exact hashes from the import/source-pack manifest.

## Safety

- Do not rename, move, delete, trash, or deduplicate documents outside the requested folder unless explicitly asked.
- Prefer reversible organization: move into subfolders and preserve manifests.
- Never delete originals as part of renaming. Disposal/trash is a separate explicit cleanup step with its own manifest.
- Keep private details out of public branch names, commit messages, issue titles, and PR titles.
- For high-stakes documents, preserve enough evidence for the human to understand why the name was chosen.
