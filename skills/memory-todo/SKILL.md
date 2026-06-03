---
name: memory-todo
description: Use this skill when the user wants a durable Markdown/wiki-native todo system in workspace or agent memory files, especially to add, update, complete, archive, review, or brief tasks from files such as memory/todo.md or memory/todo/. Apply it for memory-backed task tracking, compact dashboards, exact reminder/review scheduling decisions, and task hygiene without SQLite, JSON databases, external project managers, or full task-list promotion into MEMORY.md.
---

# Memory Todo

## Goal

Maintain a readable Markdown todo system whose source of truth stays in workspace/memory files. Prefer simple text that survives agent restarts, git diffs, wiki browsing, and manual edits.

## Default layout

Use the existing layout if one is already present. For a new system, prefer:

```text
memory/todo.md                 # compact dashboard/index only
memory/todo/inbox.md           # uncategorized or newly captured tasks
memory/todo/<area-or-project>.md
memory/todo/archive/YYYY.md    # completed or obsolete tasks
```

Do not introduce SQLite, JSON state, hidden caches, external task managers, or generated databases unless the user explicitly asks. `MEMORY.md` may mention that a todo system exists, but do not copy full task lists into long-term memory.

## Task block format

Keep tasks readable and stable. Preserve the task's original language by default; translate only when the user requests it. Use checkboxes for scanability and metadata lines for consistency:

```markdown
### [ ] <original-language task title>
- Status: open | next | in-progress | waiting | scheduled | done | archived
- Priority: P1 | P2 | P3 | someday
- Area/Project: <area or project, if known>
- Due: <YYYY-MM-DD HH:mm TZ or none>
- Reminder: <exact reminder/review request or none>
- Source: <short private-safe pointer, message/file/link/date if useful>
- Next action: <one concrete next step, if known>
- Waiting/blockers: <who/what is blocking, if any>
- Notes:
  - <dated concise notes only when useful>
```

Omit unknown metadata rather than inventing it, but keep `Status`, `Priority`, and `Next action` when they are inferable. Avoid renumbering or rewriting unrelated tasks.

## Workflow

### 1. Inspect first

- Read `memory/todo.md` and the likely detailed file under `memory/todo/` before editing.
- Search existing todo files for duplicates, prior context, or completed versions of the same task.
- If the destination area is unclear, use `memory/todo/inbox.md`; ask only when ambiguity would cause real harm.

### 2. Start tracked work

When the user asks you to start, continue, work on, or execute work that clearly maps to an existing todo task:

- update the task before substantial work begins, unless the user explicitly asked not to edit todo files;
- set `Status: in-progress` when the local todo vocabulary supports it; otherwise use the nearest local equivalent and preserve existing conventions;
- add a dated note stating that work started, the concrete trigger/source, and the immediate execution target;
- refresh `memory/todo.md` or the dashboard if the task is visible there, so the compact view no longer says merely "next" or "planned";
- if the work completes in the same turn, update the task again to `done`, `waiting`, or the appropriate next state with evidence and paths.

Do not mark exploratory questions, brainstorming, or "what would you need?" conversations as `in-progress` unless the user also asks you to begin the work.

### 3. Add or update tasks

- Add new tasks to the relevant area/project file, not directly to `MEMORY.md`.
- Update an existing task in place when it is clearly the same work.
- Preserve the user's wording and language for the title and important details.
- Record due dates/reminders exactly as stated; include timezone when known.
- Keep sensitive details in the detailed task file only when necessary, and use neutral pointers on the dashboard.

### 4. Maintain the dashboard

`memory/todo.md` should be a compact operating view, not the full database. Include only:

- urgent/overdue/high-priority tasks;
- upcoming due items and exact reminders/reviews;
- a few active next actions per major area;
- links or relative paths to detailed todo files;
- a short review timestamp or maintenance note when useful.

Remove or collapse completed, stale, and low-priority details from the dashboard after updating their source task blocks.

### 5. Complete and archive

When a task is done:

- change `[ ]` to `[x]` and set `Status: done`;
- add `Completed: YYYY-MM-DD` when practical;
- remove it from the dashboard unless it is useful as a recent completion note;
- archive done/obsolete tasks into `memory/todo/archive/YYYY.md` during cleanup, preserving source, completion date, and any important final note.

Do not delete a task's history just to make the dashboard cleaner.

## Reminders and reviews

A due date in Markdown is descriptive state, not a timer. Use cron/reminder tooling only when the user explicitly requests an exact reminder/review or clearly implies one, such as "remind me tomorrow at 9" or "review this every Friday".

When creating scheduled work:

- use the exact requested schedule and timezone;
- use a neutral, private-safe name/label such as `todo-review-weekly`, not sensitive task contents;
- point the reminder/review back to the Markdown todo file;
- do not emulate timers with repeated ad-hoc heartbeat checks.

## Review modes

Use these modes when the user asks for task review, planning, or briefing:

- **Manual review:** inspect dashboard plus active area files; report open, waiting, overdue, and unclear tasks.
- **Daily briefing:** highlight today/overdue items, exact reminders, and 1-3 realistic next actions.
- **Evening prep:** focus on tomorrow, blocked items, and setup actions that reduce morning friction.
- **Weekly quiet review:** archive completed work, refresh priorities, move stale items to someday/archive, and compact the dashboard.

Keep review outputs concise and actionable. Save durable changes only in Markdown todo files.

## Privacy and safety

- Treat todo files as private memory. Do not expose private task details in generic examples, cron labels, session labels, branch names, or public commit messages.
- Use private-safe pointers for sources: `private message, 2026-05-20`, `email thread`, `memory/path.md`, or a redacted link when needed.
- Do not send messages, create external calendar events, or modify third-party project managers unless the user explicitly asks.
- If a task involves credentials, legal/medical/financial issues, or another person's private details, keep dashboard wording especially neutral.

## Validation checklist

Before finishing a todo-maintenance turn, verify:

- Markdown files remain the source of truth; no hidden database/state was added.
- Existing related tasks were checked to avoid duplicates.
- Task language was preserved unless translation was requested.
- Status, priority, due/reminder, area/project, source, next action, and blockers were captured when known.
- `memory/todo.md` stayed compact and points to detailed files instead of copying everything.
- Completed tasks were marked done and removed/collapsed from the dashboard.
- Archived tasks retained enough context to recover why they existed.
- Any cron/reminder was exact, requested or clearly implied, timezone-aware, and private-safe.
