---
name: openclaw-session-indexing
description: Build and maintain compact, privacy-conscious sidecar indexes for OpenClaw sessions without modifying OpenClaw source code or routine session stores. Use when asked to find, recall, inventory, title, review, or prepare safe cleanup/archive candidates for existing OpenClaw sessions, dashboard sessions, subagents, cron sessions, or stored conversation history while preserving only unique unsaved content and avoiding redundant transcript summaries.
---

# OpenClaw Session Indexing

## Goal

Make existing OpenClaw sessions easier to find and reason about using sidecar indexes, without patching OpenClaw source/product code and without routine `sessions.json` edits.

This skill is for **read-first session recall and review**. It complements `openclaw-session-labeling`, which handles labels/names for newly-created work.

## Hard boundaries

Do not:

- edit OpenClaw source code, installed `/app/dist`, or local OpenClaw product bundles;
- maintain a local OpenClaw fork/patch set for session labels;
- routinely edit `sessions.json` to label sessions;
- delete, archive, or hide sessions as part of this indexing skill;
- summarize whole transcripts by default;
- copy secrets, private identifiers, credentials, personal names, or sensitive medical/legal/financial/security details into the index.

If the user asks for archive/delete/hide, produce a read-only review plan first. Mutations require a separate explicit confirmation and a backup/reversible archive workflow.

## Default workflow

1. **Choose the index target**
   - Default path: `memory/openclaw/session-index-YYYY-MM-DD.md` in the active workspace.
   - If an index already exists for the same purpose/date, update it instead of creating a near-duplicate.

2. **Collect session metadata read-only**
   - Prefer first-class session tools when available (`sessions_list`, `sessions_history`) for visible sessions.
   - Otherwise use read-only CLI output such as `openclaw sessions --json`.
   - Include all agents only when requested or useful; otherwise keep scope narrow.

3. **Infer minimal titles/topics**
   - Use labels, display names, derived titles, latest user-visible context, or a small history sample.
   - When reading history, use a tight limit and avoid tool messages unless needed.
   - Do not inspect transcript content more deeply than needed to identify the session.

4. **Write/update a compact sidecar index**
   - Map session keys to short topics, dates, surfaces/kinds, status, and action notes.
   - Include source/provenance: command/tool used, timestamp, store path if known.
   - Keep entries short. Prefer pointers over copied content.

5. **Apply the dedup rule**
   - Before saving content from a session, check whether it is already saved or implemented elsewhere: memory files, TODOs, reports, commits/PRs, durable artifacts, or canonical notes.
   - Save only unique unsaved deltas: decisions, blockers, instructions, unresolved TODOs, or work products not already represented elsewhere.
   - If content is already captured, keep only a compact pointer if useful.

6. **Recommend next actions without mutating**
   - Mark candidates as `keep`, `review`, `archive-candidate`, or `cleanup-candidate`.
   - Protect main/current/active sessions by default.
   - Treat cleanup as a later guarded workflow, not part of indexing.

## Suggested index structure

Use this structure unless the user asks for a different one:

```markdown
# OpenClaw session index — YYYY-MM-DD

Generated: <timestamp>
Scope: <agent/store/filter>
Mode: read-only sidecar index

## Notes
- This file is a sidecar recall aid, not OpenClaw runtime state.
- It should not contain secrets or private transcript dumps.

## Sessions
| Title | Session key | Kind | Updated | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| short-topic | `agent:...` | direct/subagent/cron/... | ISO/date | keep/review | compact pointer |

## Cleanup/archive candidates
| Candidate | Reason | Required confirmation before mutation |
| --- | --- | --- |

## Unsaved deltas preserved
- Only list content not already captured elsewhere.

## Source provenance
- Tool/command used: ...
- Existing indexes checked: ...
```

## Helper script

Use `scripts/render_session_index.py` to convert `openclaw sessions --json` metadata into a Markdown starter index without reading transcripts:

```bash
openclaw sessions --json --limit 100 > /tmp/openclaw-sessions.json
python3 <skill-dir>/scripts/render_session_index.py /tmp/openclaw-sessions.json \
  --protect-key agent:<agent-id>:main \
  --output memory/openclaw/session-index-$(date +%F).md
```

The script is metadata-only. It redacts local store paths by default; add `--include-store-paths` only for private local indexes where the exact path is useful. Add `--protect-key` for the current session or other sessions that must not be cleanup candidates. After rendering, add or refine titles from minimal context if needed.

## Cleanup/archive review rules

If the user asks whether sessions can be cleaned up:

- stay read-only unless the user explicitly approves mutation;
- identify active/current/main sessions and mark them protected;
- separate `safe-to-ignore`, `needs-review`, and `archive-candidate`;
- verify the content-preservation/dedup rule before recommending archive;
- prefer reversible archive/hide over permanent deletion;
- require backup paths and explicit confirmation before any runtime-data mutation;
- direct store edits are last-resort repair actions only, not normal workflow.

## Completion checklist

Before reporting completion:

- index written or updated at a clear path;
- no OpenClaw source/product files modified;
- no routine `sessions.json` edits performed;
- any transcript/history inspection was minimal and justified;
- redundant content was skipped or replaced by a compact pointer;
- main/current/protected sessions are marked as protected when identifiable;
- local store paths are redacted unless intentionally included for a private local index;
- unresolved review/archive candidates are clearly marked, not silently mutated.
