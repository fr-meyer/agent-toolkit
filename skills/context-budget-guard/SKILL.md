---
name: context-budget-guard
description: Enforce size limits for context-injected, bootstrap, memory, profile, prompt, or long-term note files before they bloat agent startup context. Use when editing files such as MEMORY.md, AGENTS.md, USER.md, SOUL.md, system/profile notes, curated memory summaries, skill-visible docs, or any file with a byte/character/token budget; use when a warning mentions overcontext, truncation, context budget, bootstrap limit, or oversized injected context; use after modifying such files to check size, archive details, split content into topic files, and keep only compact pointers in the context-loaded file.
---

# Context Budget Guard

## Goal

Keep files that are loaded into an agent's context small, stable, and pointer-based. Prevent detailed logs, copied transcripts, command dumps, and auto-promoted memory blocks from bloating bootstrap context or causing truncation.

This skill is general-purpose: apply it to any context-loaded file with a known or implied budget, not only `MEMORY.md`.

## Default Limits

Use the most specific limit available from project instructions, config, or the user's warning.

If no limit is provided:
- hard limit: `12000` bytes
- target size: `10000` bytes
- measurement: bytes first, characters as secondary diagnostic

Never assume a token budget is equivalent to a byte or character budget. If only a token budget is known, use the configured tool/token counter when available; otherwise use byte and character checks as conservative proxies and say so.

## Workflow

### 1. Identify guarded files

Treat a file as guarded when any of these are true:
- it is loaded automatically at session/bootstrap/startup
- it is included in model context by default
- it is a curated long-term memory or profile file
- it has an explicit size/token/character limit
- a runtime warning mentions truncation, overcontext, or context injection for the file

Common examples: `MEMORY.md`, `AGENTS.md`, `USER.md`, `SOUL.md`, profile/system notes, compact project context files, skill-visible summaries, and curated memory indexes.

### 2. Check before and after editing

Before editing, measure size if the current state matters.
After every edit to a guarded file, run the bundled checker or equivalent:

```bash
python3 <skill-dir>/scripts/check_context_budget.py MEMORY.md --limit 12000 --target 10000
```

For multiple files:

```bash
python3 <skill-dir>/scripts/check_context_budget.py AGENTS.md MEMORY.md USER.md --limit 12000 --target 10000
```

If the project specifies a different limit, pass that limit explicitly.

### 3. If over budget, archive then compact

Do not simply delete useful knowledge. Preserve detail outside the guarded file, then replace detail with compact pointers.

Preferred sequence:
1. Create a dated snapshot or move detailed sections to an appropriate topic/daily file.
2. Keep the guarded file as a concise index of durable facts and paths.
3. Replace long narratives with one-line pointers to source files.
4. Remove duplicated promoted excerpts, command logs, transcripts, raw outputs, and stale implementation details.
5. Re-run the size check.
6. Repeat until under hard limit; aim for target size when practical.

Good archive destinations:
- daily logs: `memory/YYYY-MM-DD.md`
- topic notes: `memory/<topic>/...`
- project runbooks: `memory/openclaw/...`
- reports/evidence folders for long analyses

### 4. Keep the guarded file pointer-first

Prefer this pattern:

```md
- Short durable fact or decision: `path/to/details.md`.
```

Avoid this pattern in guarded files:

```md
- Full transcript, long copied article, tool logs, multi-page report, command output, or repeated daily excerpts...
```

### 5. Validate and report

Before finishing, report:
- final size and limit
- whether the file is under hard limit
- archive or topic paths used
- any unresolved over-budget file as `[blocked]` with the missing decision or compression tradeoff

## Compaction Heuristics

Keep in the guarded file:
- durable preferences and stable policies
- canonical source paths
- current active decisions
- small lists that are frequently needed at startup
- pointers to detailed evidence

Move out of the guarded file:
- raw logs and command output
- articles, transcripts, recipes, travel plans, watchlists, and long reports
- repeated auto-promoted memory excerpts
- historical debugging details not needed every session
- anything already recoverable by search from `memory/` or project files

When unsure, prefer preserving the detail in a topic file and keeping a compact pointer.

## Bundled Script

Use `scripts/check_context_budget.py` to measure files deterministically and fail fast when a file exceeds its hard limit. The script prints bytes, characters, line count, and status for each file, and exits non-zero on over-limit files.
