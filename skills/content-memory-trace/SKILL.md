---
name: content-memory-trace
description: Use this skill when a user shares or references content and wants the agent to preserve a durable, privacy-conscious trace so future sessions can resume the discussion. Apply it for links, articles, PDFs, papers, videos, images, uploaded documents, social posts, datasets, code snippets, or other source material when the task involves remembering what was inspected, recording provenance, saving notes, creating source/artifact pointers, or leaving resume keywords. Do not use it as a substitute for source-specific ingestion, transcript, PageIndex, research-paper, or summarization skills; delegate to those first when they fit and use this skill to record the trace around them.
---

# Content Memory Trace

## Goal

Preserve a compact, useful trace of shared content: what the source was, how it was accessed, why the user cared, what artifacts were created, and how a future session can resume without rereading the original chat.

This skill is a provenance and memory-hygiene wrapper. It should not become a full archive of the content unless the user explicitly requested that and the content is safe to store.

## Default workflow

### 1. Identify the content and intent

For each source, capture enough identity to find it again:

- source kind: URL, uploaded file, local path, PageIndex document, YouTube video, social post, dataset, image, pasted text, etc.
- canonical source locator when available: URL, platform ID, DOI, filename, document ID, archive/report path, or verified local path
- title/label, author/publisher/channel, date, version, and language when known
- user intent: why the user shared it and what question, decision, project, or output it supports
- access status: resolved, partially resolved, blocked, paywalled, removed, ambiguous, login-required, file unavailable, or tool unavailable

If the source cannot be accessed or resolved, still write the trace with the blocker and the exact uncertainty. Do not pretend the content was inspected.

### 2. Prefer specialized source workflows

Before writing substantial notes, route through the most specific workflow available:

- YouTube captions/transcripts → use `youtube-transcript-archive`; trace the video ID, selected language, transcript source, report path, and manifest path.
- Public PDF URLs or papers that should live in PageIndex → use `pageindex-ingest-paper-urls`; trace duplicate checks, target folder, PageIndex document name/id, and processing status.
- Already-resolved PageIndex papers → use PageIndex find/read/summarize skills as appropriate; trace verified filenames, pages/coverage, and report paths.
- Zotero-derived PDFs → use `zotero-docai-ingest-to-pageindex`; trace Zotero item/attachment identifiers and verified bridge rows.
- Research-paper summaries, classifications, or literature reviews → use the relevant paper/literature skill for the deliverable; trace the resulting report paths and source set.
- Other source-specific tools or skills → use them when they provide better provenance, extraction, or safety behavior than ad hoc notes.

Record the artifact outputs from those workflows instead of duplicating their full contents in memory.

### 3. Choose a safe trace destination

Use the most appropriate durable note location available from user/project context:

1. explicit user-provided path or project convention
2. active project/topic note, source log, or research log
3. daily note such as `memory/YYYY-MM-DD.md` in the active workspace

If no trusted writable memory location exists, ask before writing. Do not hardcode host-specific absolute paths in reusable instructions.

Keep detailed trace notes in daily/topic/project files. Add to `MEMORY.md` only when the source or project is durable enough to matter across sessions; keep that entry as a compact pointer, not detailed content. When editing any context-loaded memory file such as `MEMORY.md`, follow the local context-budget rules and validate its size when required.

### 4. Write the trace note

Append or update a concise note. Prefer updating an existing note for the same source instead of creating near-duplicates.

Use this template unless the project already has a better format:

```md
## Content trace — <short title or source label>

- Date captured: <YYYY-MM-DD HH:MM timezone or available session date>
- User intent: <why this source was shared / what question it supports>
- Source kind: <article | PDF | video | image | dataset | social post | uploaded doc | other>
- Source locator: <canonical URL, DOI, video ID, filename, PageIndex doc name/id, or redacted/private locator>
- Access/resolution status: <resolved | partial | blocked | ambiguous> — <brief evidence or blocker>
- Context: <1-3 bullets summarizing what mattered in the conversation, not a transcript dump>
- Artifacts created or reused:
  - <path/id/link to report, archive, PageIndex doc, cleaned transcript, extracted data, screenshot analysis, etc.>
- Key observations:
  - <only stable, useful findings; avoid full copied content>
- Privacy/sensitivity notes: <public | private | sensitive | unknown; redactions or storage limits>
- Resume keywords: <5-12 keywords, names, IDs, titles, project tags, or phrases>
- Next step / open question: <optional>
```

For multiple sources, create one compact entry per source plus a short collection-level note if the sources belong together.

### 5. Apply privacy and copyright discipline

- Do not copy full private, sensitive, paywalled, copyrighted, personal, medical, legal, financial, security, or credential-containing content into long-term memory by default.
- Store pointers, metadata, short context, and artifact paths instead of raw content.
- Redact secrets, tokens, private contact details, and unnecessary local paths.
- If the user explicitly asks to preserve full content, confirm that it is safe and allowed, then store it outside compact long-term memory in a clearly named artifact file.
- Preserve uncertainty: distinguish observed facts, user-provided claims, and agent inferences.
- Do not bypass paywalls, login walls, robots restrictions, or access controls to build a trace.

### 6. Confirm to the user

Keep the final confirmation short and useful:

```md
Saved a durable trace for `<source label>`.
- Trace note: `<path>`
- Source status: <resolved | partial | blocked> — <one-line detail>
- Artifacts: <paths/IDs or "none created">
- Resume keywords: <comma-separated keywords>
```

If blocked, say what is missing and what would unblock future work. If no file was written because the user only asked for ephemeral help or no trusted destination exists, say that clearly.

## Completion checklist

Before finishing:

- source locator and access status are recorded
- user intent and short context are recorded
- specialized workflow outputs are referenced instead of duplicated
- artifacts created/reused are listed with paths or IDs
- sensitive/private full content is not copied into long-term memory by default
- uncertainty and blockers are explicit
- resume keywords are included
- any `MEMORY.md` update is compact and budget-checked when local rules require it
