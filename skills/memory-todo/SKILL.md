---
name: "memory-todo"
description: "Keep Markdown as durable todo source while coordinating qualifying active work through source-linked Workboard cards."
---

# Memory Todo

## Goal

Maintain a readable Markdown todo system whose durable source of truth stays in workspace/memory files. Prefer simple text that survives agent restarts, git diffs, wiki browsing, and manual edits.

Use Workboard as the live execution and coordination layer only when tracked work is multi-turn, waiting on approval or input, handed off, dependency-linked, or expected to produce review or proof. A Workboard card supplements the durable Markdown record; it never replaces it.

## Default layout

Use the existing layout if one is already present. For a new system, prefer:

```text
memory/todo.md                 # compact dashboard/index only
memory/todo/inbox.md           # uncategorized or newly captured tasks
memory/todo/<area-or-project>.md
memory/todo/archive/YYYY.md    # completed or obsolete tasks
```

Do not introduce SQLite, JSON task state, hidden caches, generated databases, or third-party project managers as the durable todo source unless the user explicitly asks. Workboard may hold live execution state under the operating split below. `MEMORY.md` may mention that a todo system exists, but do not copy full task lists into long-term memory.

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
- Workboard: <card id or private-safe link, only when active and useful>
- Next action: <one concrete next step, if known>
- Waiting/blockers: <who/what is blocking, if any>
- Notes:
  - <dated concise notes only when useful>
```

Omit unknown metadata rather than inventing it, but keep `Status`, `Priority`, and `Next action` when they are inferable. Avoid renumbering or rewriting unrelated tasks.

## Operating split: durable Markdown and live Workboard

### When a Workboard card is warranted

Create or reuse a Workboard card when durable tracked work becomes active and is any of the following:

- multi-turn;
- waiting on approval, input, or an external dependency;
- handed off between workers or sessions;
- dependency-linked;
- expected to produce review, proof, or artifacts.

Do not create cards for trivial one-turn answers or bulk-promote the backlog. Do not migrate every existing Markdown task merely because Workboard is available.

### Source-linked, idempotent cards

For qualifying work:

1. Inspect the durable task first and search Workboard for an existing card linked to the same source path and task identity.
2. Reuse that card when it represents the same active work. Otherwise create exactly one card with a stable, private-safe source pointer such as `memory/todo/<file>.md#<task-anchor>` or the nearest unambiguous file/task reference.
3. Keep the full commitment, approval gates, decisions, and cross-project context in Markdown. Put only the concise execution objective, current state, source pointer, dependencies, and proof/artifact references on the card.
4. Record the card id or private-safe link in Markdown only when it materially helps coordination.

Never copy the full task prose into both systems. Never create multiple cards for the same source task merely because a run, worker, or session changed.

### Mandatory Workboard lifecycle

Before substantive execution on a qualifying card:

1. Claim the card.
2. Keep the claim truthful with heartbeats during long work.
3. Add concise progress, dependency, proof, and artifact references as work advances.
4. End every claim intentionally with exactly one lifecycle outcome:
   - complete when the objective and agreed evidence gates are satisfied;
   - block when a real blocker or approval gate prevents continuation;
   - release or hand off when pausing without claiming completion.
5. Do not leave a stale claim when execution stops.

Prefer native Workboard diagnostics for stale, stranded, blocked-too-long, repeated-failure, and missing-proof work before adding custom polling or cron automation.

### Completion, acceptance, synchronization, and archive

Workboard proof is not by itself durable closeout. When completion requires Franck's acceptance or another explicit review gate, keep the card in review/waiting state rather than treating proof submission as acceptance.

After completion is accepted under the applicable user-approved or pre-agreed evidence gate:

1. Update the source Markdown task with the concise accepted outcome, final status, completion date when practical, and useful evidence/artifact pointers.
2. Refresh or remove its dashboard entry as appropriate.
3. Only after that Markdown synchronization, complete and/or archive the Workboard card according to the available lifecycle.
4. Archive the Markdown task during normal cleanup while retaining enough history to recover why it existed and how it ended.

Never archive the card first and promise to update Markdown later.

### Approval and safety gates

A card, assignment, claim, ready status, dependency transition, or dispatch request never grants approval. Preserve all existing approval, safety, privacy, destructive-action, credential, legal/medical/financial, external-write, and publication gates from the durable task and higher-priority policy.

If work reaches a gate, record the exact blocker or approval needed, synchronize the durable task, then block or intentionally release the card. Do not infer approval from card state or from earlier approval with a narrower scope.

### Safe fallback when Workboard is unavailable

If Workboard tools or service are unavailable:

- continue safe, authorized work using the durable Markdown task as the execution record;
- record start, current state, heartbeat-equivalent dated progress notes when useful, blockers, next action, and proof/artifact pointers in Markdown;
- preserve the same complete/block/release-or-handoff discipline in the task status and notes;
- state that Workboard synchronization could not run;
- do not invent a card id, claim, heartbeat, completion, or archive state;
- when Workboard returns, create or reuse one source-linked card only if the work still qualifies and remains active; do not backfill the whole backlog or duplicate completed prose.

## Workflow

### 1. Inspect first

- Read `memory/todo.md` and the likely detailed file under `memory/todo/` before editing.
- Search existing todo files for duplicates, prior context, or completed versions of the same task.
- If active work qualifies for Workboard, also search for a source-linked card before creating one.
- If the destination area is unclear, use `memory/todo/inbox.md`; ask only when ambiguity would cause real harm.

### 2. Start tracked work

When the user asks to start, continue, work on, or execute work that clearly maps to an existing todo task:

- update the task before substantial work begins, unless the user explicitly asked not to edit todo files;
- set `Status: in-progress` when the local todo vocabulary supports it; otherwise use the nearest local equivalent and preserve existing conventions;
- add a dated note stating that work started, the concrete trigger/source, and the immediate execution target;
- refresh `memory/todo.md` or the dashboard if the task is visible there, so the compact view no longer says merely `next` or `planned`;
- if the work qualifies for Workboard, create or reuse the idempotent source-linked card and claim it before substantive execution;
- if the work completes in the same turn, update the task again to `done`, `waiting`, or the appropriate next state with evidence and paths, and close the claim intentionally.

Do not mark exploratory questions, brainstorming, or `what would you need?` conversations as `in-progress` unless the user also asks you to begin the work.

### 3. Add or update tasks

- Add new tasks to the relevant area/project file, not directly to `MEMORY.md`.
- Update an existing task in place when it is clearly the same work.
- Preserve the user's wording and language for the title and important details.
- Record due dates/reminders exactly as stated; include timezone when known.
- Keep sensitive details in the detailed task file only when necessary, and use neutral pointers on the dashboard and Workboard card.
- Do not create a Workboard card until the work is active and qualifies.

### 4. Maintain the dashboard

`memory/todo.md` should be a compact operating view, not the full database. Include only:

- urgent/overdue/high-priority tasks;
- upcoming due items and exact reminders/reviews;
- a few active next actions per major area;
- links or relative paths to detailed todo files;
- a short review timestamp or maintenance note when useful.

Remove or collapse completed, stale, and low-priority details from the dashboard after updating their source task blocks. Do not turn the dashboard into a mirror of Workboard.

### 5. Complete and archive

When a task is accepted as done:

- change `[ ]` to `[x]` and set `Status: done`;
- add `Completed: YYYY-MM-DD` when practical;
- add concise final evidence or artifact pointers when useful;
- remove it from the dashboard unless it is useful as a recent completion note;
- if linked to Workboard, synchronize these accepted results before completing or archiving the card;
- archive done/obsolete tasks into `memory/todo/archive/YYYY.md` during cleanup, preserving source, completion date, and any important final note.

Do not delete a task's history just to make the dashboard cleaner.

## Reminders and reviews

A due date in Markdown is descriptive state, not a timer. Use cron/reminder tooling only when the user explicitly requests an exact reminder/review or clearly implies one, such as `remind me tomorrow at 9` or `review this every Friday`.

When creating scheduled work:

- use the exact requested schedule and timezone;
- use a neutral, private-safe name/label such as `todo-review-weekly`, not sensitive task contents;
- point the reminder/review back to the Markdown todo file;
- do not emulate timers with repeated ad-hoc heartbeat checks;
- do not create a Workboard card solely because a reminder exists; create one only when the resulting work becomes active and otherwise qualifies.

## Review modes

Use these modes when the user asks for task review, planning, or briefing:

- **Manual review:** inspect dashboard plus active area files; report open, waiting, overdue, and unclear tasks.
- **Daily briefing:** highlight today/overdue items, exact reminders, and 1-3 realistic next actions.
- **Evening prep:** focus on tomorrow, blocked items, and setup actions that reduce morning friction.
- **Weekly quiet review:** archive completed work, refresh priorities, move stale items to someday/archive, compact the dashboard, and inspect qualifying active cards for stale claims or missing proof.

Keep review outputs concise and actionable. Save durable commitment and closeout changes in Markdown todo files; keep transient coordination details on Workboard.

## Privacy and safety

- Treat todo files and linked Workboard cards as private operational memory.
- Do not expose private task details in generic examples, cron labels, session labels, branch names, card titles, or public commit messages.
- Use private-safe pointers for sources: `private message, 2026-05-20`, `email thread`, `memory/path.md`, or a redacted link when needed.
- Do not send messages, create external calendar events, or modify third-party project managers unless the user explicitly asks.
- If a task involves credentials, legal/medical/financial issues, or another person's private details, keep dashboard and card wording especially neutral.

## Validation checklist

Before finishing a todo-maintenance or todo-execution turn, verify:

- Markdown files remain the durable source of truth; no hidden database/state replaced them.
- Existing related tasks were checked to avoid duplicates.
- No bulk backlog migration or duplicate full prose was introduced.
- Qualifying active work has one reused or newly created source-linked Workboard card when Workboard is available.
- Every substantive card execution was claimed, heartbeated when long-running, supplied with concise proof/artifact references, and ended with complete, block, or intentional release/handoff.
- Workboard state did not bypass any approval or safety gate.
- Accepted completion was synchronized to Markdown before card completion/archive.
- If Workboard was unavailable, Markdown captured truthful lifecycle state and no card state was invented.
- Task language was preserved unless translation was requested.
- Status, priority, due/reminder, area/project, source, next action, and blockers were captured when known.
- `memory/todo.md` stayed compact and points to detailed files instead of copying everything.
- Completed tasks were marked done and removed/collapsed from the dashboard.
- Archived tasks retained enough context to recover why they existed.
- Any cron/reminder was exact, requested or clearly implied, timezone-aware, and private-safe.
