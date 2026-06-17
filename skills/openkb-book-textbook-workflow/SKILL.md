---
name: openkb-book-textbook-workflow
description: Use this skill when the user needs to turn books, textbooks, manuals, or course packs into structured OpenKB/PageIndex knowledge workflows with source inventory, collection/book cards, lesson or chapter maps, bottom-up summaries, and optional hierarchy/retrieval comparisons. Do not use it for ordinary single-document ingest, research-paper classification, or paper-only Page Index workflows.
---

# OpenKB Book/Textbook Workflow

## Goal

Help the agent turn long structured books, textbooks, manuals, and course packs into reusable, source-grounded knowledge artifacts.

This skill owns the book/textbook structure and deliverables. It delegates canonical ingest, source packs, extraction, and guarded export to source-system skills such as `openkb-pageindex-docai`.

## Use This Skill For

- Books, textbooks, manuals, course packs, language-learning materials, and multi-volume learning collections.
- Requests to build source inventories, collection cards, book cards, lesson maps, chapter maps, lesson cards, chapter cards, bottom-up summaries, or practice/study packs from long structured material.
- Follow-up work after OpenKB/PageIndex ingest where the corpus needs book-aware organization rather than paper-style summaries.
- Optional hierarchy experiments such as a ConDB comparison, when the corpus has a meaningful tree.

## Do Not Use This Skill For

- Ordinary OpenKB/PageIndex ingest without book, chapter, lesson, or collection structure.
- Research-paper discovery, full-paper read verification, paper classification, or paper summary wrappers; use the relevant paper skills instead.
- A broad literature review or cross-paper synthesis; use `literature-review`.
- Standalone local-folder cleanup or renaming; use `document-renaming`.
- Remote/cloud PageIndex MCP experiments for private corpora.

## Required Inputs

Gather or infer:

- corpus path, document list, or already-ingested source-pack identities;
- desired output folder or project folder;
- corpus purpose: learning, reference, operational manual, class prep, research reading, or another purpose;
- sensitivity/privacy level and whether work must stay local;
- target outcome: searchable knowledge base, study kit, lesson/chapter map, reading guide, QA deck, or other pack;
- optional lanes to run: ConDB hierarchy comparison, ChatIndex bounded recall, or local PageIndex MCP after a local migration target exists.

If the output folder is not explicit and cannot be inferred from trusted project context, ask before writing files.

## Default Workflow

### 1. Lock Scope

- State the corpus, purpose, desired output, sensitivity, and optional lanes.
- Decide whether this is a one-off project or should produce reusable artifacts.
- Identify existing source-system authority, such as OpenKB source packs, PageIndex state, local files, Zotero, or URLs.

### 2. Prepare Sources

- For local human-facing folders, delegate to `document-renaming` before ingest unless the user explicitly wants originals left untouched.
- For canonical ingest, delegate to `openkb-pageindex-docai` or the relevant source-system skill.
- Keep route evidence, selected reconstruction, provenance, hashes, source-pack identity, and import manifests.
- Do not make remote/cloud PageIndex MCP a dependency for private source ingestion.

### 3. Inventory and Group the Corpus

Create `source-inventory.md` and, when useful, `source-inventory.json`.

Track:
- filename or source identity;
- source hash or stable document id;
- title, edition/version, language, page count when known;
- role in the collection: main text, workbook, grammar/vocabulary supplement, answer key, teacher guide, reference, appendix, duplicate, or background;
- canonical evidence path or source-system pointer;
- sensitivity and rebuild/recovery notes.

Group related volumes before summarizing them.

### 4. Build Collection and Book Cards

Create a collection card and one compact card per book or volume.

Each card should include:
- title and normalized short name;
- role in the collection;
- audience/level;
- scope and main topics;
- relation to other volumes;
- best use cases;
- source authority and provenance pointer;
- known gaps or quality warnings.

### 5. Build Lesson or Chapter Maps

Create `lesson-map.md` / `chapter-map.md` and a machine-readable equivalent when useful.

Use stable fields:
- volume/book;
- lesson/chapter number;
- title;
- topic/domain;
- functions, tasks, procedures, or learning outcomes;
- grammar/concepts/vocabulary where relevant;
- page or source pointers;
- tags and usefulness for the user's goal;
- links to related supplement material.

Preserve enough structure that a later agent can answer "which lesson or chapter should I use for this task?" without rereading the full corpus.

### 6. Create Working-Grain Cards

For textbooks, create lesson cards when useful:
- outcomes;
- key expressions;
- grammar or concepts;
- vocabulary domains;
- dialogues, examples, activities, exercises, and source pointers;
- practical usefulness notes.

For manuals or books, create chapter cards:
- core ideas or procedures;
- examples and caveats;
- figures/tables to revisit;
- page ranges or source pointers;
- relation to other chapters.

### 7. Summarize Bottom-Up

Summarize from the lowest useful grain upward:

1. page, section, or activity;
2. lesson or chapter;
3. book or volume;
4. collection.

Keep source pointers at the lowest useful grain. Do not replace evidence with a detached top-level summary.

### 8. Produce the User-Facing Pack

Tailor the final output to the actual job:
- study kit;
- role-play scripts;
- flashcards;
- practice drill;
- reading guide;
- lookup index;
- QA deck;
- executive guide.

Keep the pack practical. Do not dump every intermediate artifact into the final answer unless the user asked for an audit trail.

### 9. Optional ConDB Comparison

Run this only when hierarchy matters.

- Build or use a small tree over the relevant book structure.
- Ask 3-5 task-shaped hierarchy questions.
- Compare against OpenKB/source Markdown and direct text search.
- Record whether the tree helps, misses branches, or creates false positives.
- Treat ConDB as an optional comparison layer unless a later decision explicitly promotes it.

### 10. Optional ChatIndex Bounded Recall

Use ChatIndex only for bounded workflow-memory or long-thread decision recall.

- Keep slices bounded.
- Compare with memory notes and direct text search.
- Do not wire ChatIndex into OpenKB/PageIndex/ConDB production flows.

### 11. Optional Local PageIndex MCP Check

Only consider PageIndex MCP after a local/self-managed PageIndex or OpenKB/PageIndex target exists.

- Prefer local read-only checks.
- Do not use deprecated remote/cloud MCP endpoints for private corpora.
- Compare MCP behavior against native OpenKB/PageIndex outputs and source-pack evidence.

### 12. Completion Gate

Before declaring the workflow complete, verify:

- source inventory exists and matches the corpus;
- canonical ingest status is recorded or explicitly out of scope;
- collection/book cards exist or are intentionally skipped;
- lesson/chapter maps exist;
- working-grain cards exist or are intentionally skipped;
- bottom-up summaries exist or are intentionally skipped;
- user-facing output exists;
- optional ConDB, ChatIndex, or MCP lanes are either complete or marked out of scope;
- status notes or project memory were updated when the workflow is durable.

## Output Expectations

- Use Markdown for human-facing artifacts.
- Use JSON or JSONL only when machine-readable maps or manifests are useful.
- Save artifacts only in an explicit or trusted project folder.
- In the final response, report the created or updated artifact paths, optional lanes run, skipped lanes, and any remaining decision.

## Delegation Guide

- Use `openkb-pageindex-docai` for source-neutral OpenKB/PageIndex ingest, extraction, source-pack provenance, rebuild, query, and guarded export.
- Use `document-renaming` for local/user folder preparation before ingest.
- Use paper-specific skills for Page Index research-paper discovery, reading, summarization, classification, or literature review.
- Use source-system tools directly only when no skill owns that specific operation.

## Gotchas

- A book workflow is not done just because the files were indexed.
- A table of contents is not the same as a lesson/chapter map.
- Supplement volumes must be linked to the main text when they exist.
- Broad keyword matches can produce false hierarchy hits; compare against source evidence.
- Do not promote an experimental tree/retrieval layer to canonical storage without a separate decision.
- Do not hardcode local paths, private project names, personal names, provider keys, hostnames, or account-specific model aliases in shared artifacts.

## Resources

Read only when needed:
- `references/eval-prompts.json` - use when checking trigger boundaries for this skill.

Use only when creating a new project skeleton:
- `templates/book-textbook-project-template.md` - optional artifact checklist and folder layout.
