---
name: "memory-todo"
description: "Markdown todo source with mandatory source-linked Workboard cards for plan-derived and qualifying active work."
---

# Memory Todo

## Goal

Maintain a readable Markdown todo system whose durable source of truth stays in workspace/memory files. Prefer simple text that survives agent restarts, git diffs, wiki browsing, and manual edits.

Use Workboard as the live execution and coordination layer. Workboard never replaces Markdown, but plan-derived and qualifying active work must have one source-linked Workboard card before substantive execution.

## Default layout

Use the existing layout. For a new system:

```text
memory/todo.md                 # compact dashboard/index only
memory/todo/inbox.md           # uncategorized/new tasks
memory/todo/<area-or-project>.md
memory/todo/archive/YYYY.md    # completed/obsolete tasks
```

Do not introduce SQLite, JSON task state, hidden caches, generated databases, or third-party project managers as the durable todo source unless explicitly requested. `MEMORY.md` must not become the task database.

## Task block format

Preserve the user's original language and existing conventions:

```markdown
### [ ] <original-language task title>
- Status: open | next | in-progress | waiting | scheduled | done | archived
- Priority: P1 | P2 | P3 | someday
- Area/Project: <area or project, if known>
- Due: <YYYY-MM-DD HH:mm TZ or none>
- Reminder: <exact reminder/review request or none>
- Source: <short private-safe pointer>
- Workboard: <board>/<card id>, only when linked
- Workboard key: <stable idempotency/source key>, only when linked
- Workboard sync: linked | running | blocked | ready-to-close | closed, only when useful
- Next action: <one concrete next step, if known>
- Waiting/blockers: <who/what is blocking, if any>
- Notes:
  - <dated concise notes only when useful>
```

Omit unknown metadata rather than inventing it and avoid rewriting unrelated tasks.

## Mandatory plan-to-Workboard gate

Create or reuse a Workboard card **before substantive execution** when the work is an execution step derived from a plan, project todo, ordered checklist, phase, dependency, approval gate, handoff, or review plan. This applies even when the step might fit in one turn: plan-derived execution stays visible on the live board.

A card is also mandatory for multi-turn/cross-session work, approval/input or external dependencies, handoffs, dependencies, delegation/parallel work, expected review/proof/artifacts, or consequential external writes. Only trivial one-turn answers, brainstorming, and isolated read-only lookups that are not tracked-plan execution may remain cardless. Do not bulk-promote dormant backlog.

For a multi-phase plan, create one parent card and dependency-linked child cards. Do not create a card for every conversational turn or duplicate one because a worker/session changed.

## Source-linked, idempotent cards

For qualifying work:

1. Read the durable task and determine its stable source path/task anchor.
2. Derive a private-safe idempotency key, preferably `todo:<path>#<task-anchor>`.
3. Inspect Workboard for that source/key and reuse the existing card when it represents the same work.
4. Otherwise create exactly one card with the stable key, board, concise execution objective, source pointer, dependencies, and acceptance/proof expectations.
5. For planned phases, create/decompose child cards with stable child keys and parent dependencies.
6. Record board/card identity and key in Markdown when useful.

Keep full commitments, approvals, decisions, and cross-project context in Markdown. Put only concise execution state, source pointer, dependencies, and proof/artifact references on the card. Never duplicate full task prose.

## Mandatory Workboard lifecycle

Before substantive execution: claim the card. During long work: heartbeat it and add concise progress, dependency, proof, and artifact references. End every claim with exactly one outcome: complete when objective/evidence gates are met, block for a real blocker/approval gate, or release/hand off when pausing without completion. Never leave a stale claim.

Assignment, ready state, dependency transition, or dispatch request never proves work or grants approval. A done-looking card without proof and durable-todo synchronization is not a valid closeout.

## Workboard maintenance contract

Prefer native diagnostics before custom polling or duplicate state.

- Start of meaningful work: refresh diagnostics, locate/create the source-linked card, and claim it.
- Long work: heartbeat and record concise progress/blocker comments.
- Dispatcher maintenance: use configured native safe mechanics such as promoting unblocked work, reclaiming expired claims, and blocking timed-out runs.
- Daily review: find plan-derived todo work without cards, cards without durable sources, stale running claims, stranded assignments, blockers without reasons, repeated failures, and done cards missing proof or Markdown closeout.
- Weekly review: reconcile active todo and Workboard state, collapse completed dashboard entries, and inspect board status/age.

Automatic maintenance is limited to safe lifecycle mechanics. Completion, unblocking, reassignment, deletion, archival, and changes to the meaning of work remain human-gated unless explicitly authorized.

## Completion and synchronization

Workboard proof is not durable closeout. If Franck or another reviewer must accept completion, keep the card in the applicable review/waiting or blocked state. After acceptance:

1. Update source Markdown with accepted outcome, final status, date, and evidence/artifact pointers.
2. Refresh/collapse the dashboard entry.
3. Complete or archive the Workboard card only after Markdown synchronization.
4. Archive Markdown during normal cleanup while retaining recovery context.

Never archive the card first and promise to update Markdown later.

## Approval and safety gates

A card, assignment, claim, ready status, dependency transition, or dispatch request never grants approval. Preserve approval, safety, privacy, destructive-action, credential, legal/medical/financial, external-write, and publication gates. When a gate is reached, record the exact blocker/approval, synchronize Markdown, then block or release the card. Do not infer approval from card state or narrower earlier approval.

## Workboard unavailable

If Workboard is unavailable, continue safe authorized work using Markdown, recording start/current state/progress, blockers, next action, and proof. Preserve complete/block/release-or-handoff discipline, state that synchronization could not run, and never invent card state. When Workboard returns, create/reuse one source-linked card only if work remains active and qualifies; do not backfill the backlog.

## Workflow

### Inspect first

Read `memory/todo.md` and the relevant detailed file; search for duplicates, prior context, and completed versions; classify whether work is plan-derived/qualifying; and inspect Workboard for the stable source/key before creating a card. If the area is unclear, use `memory/todo/inbox.md` and ask only when ambiguity would cause real harm.

### Start tracked work

When asked to start/continue/execute work mapped to a todo task:

- update the task before substantial work unless explicitly told not to;
- set `Status: in-progress` using local vocabulary and add a dated start note;
- if qualifying, create/reuse the idempotent source-linked card **before substantive execution**, record identity when useful, and claim it;
- refresh `memory/todo.md` if visible there;
- if it completes in the same turn, synchronize accepted results to Markdown, close the claim intentionally, and add proof.

Do not mark exploratory questions/brainstorming in-progress unless asked to begin.

### Add/update and dashboard

Add tasks to area/project files, not `MEMORY.md`; update identical tasks in place; preserve wording and exact due/reminder details; keep sensitive details in detailed files with neutral card/dashboard wording. The dashboard is a compact operating view, not a Workboard mirror: include urgent/overdue/high-priority tasks, due items, a few active next actions, links, and review timestamp; collapse completed/stale/low-priority details after source updates.

### Complete/archive

When accepted as done, mark `[x]` and `Status: done`, add completion date/evidence, collapse it from the dashboard, synchronize Markdown before completing/archiving the linked card, and archive done/obsolete tasks into `memory/todo/archive/YYYY.md` with source/date/final-note context. Do not delete history.

## Reminders and reviews

A due date is descriptive, not a timer. Use cron only for explicitly requested exact reminders/reviews, with requested timezone and a neutral private-safe label. Do not create a card solely for a reminder; create one when resulting work becomes active or otherwise qualifies.

Manual review reports open/waiting/overdue/unclear tasks and qualifying active work lacking a card. Daily briefing includes relevant Workboard blockers/stranded claims. Evening prep includes blocked items and card readiness. Weekly review archives completed work, refreshes priorities, compacts the dashboard, runs todo↔Workboard reconciliation, and inspects active cards for stale claims/missing proof.

## Privacy and validation

Treat todo files and linked cards as private operational memory. Use private-safe source pointers. Do not expose private details in generic examples, labels, branch names, card titles, or public commits. Do not send messages or modify third-party managers unless explicitly asked.

Before finishing, verify Markdown remains durable source, no duplicates/bulk migration occurred, every plan-derived/qualifying active execution has one source-linked card when available, every substantive card was claimed/heartbeated/proven/closed intentionally, maintenance findings have a next action, approval gates were preserved, accepted completion was synchronized before card completion/archive, unavailable Workboard state was not invented, and dashboard/archive/reminder conventions remain valid.
