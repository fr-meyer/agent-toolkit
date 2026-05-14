---
name: openclaw-session-labeling
description: Apply consistent human-readable labels to OpenClaw work sessions, spawned subagents, detached tasks, cron jobs, reminders, and recurring agentTurn workflows. Use when creating or reviewing sessions_spawn calls, cron jobs, sessionTarget choices, background task/session naming, or policies that prevent anonymous UUID-only OpenClaw sessions.
---

# OpenClaw Session Labeling

## Goal

Make newly created OpenClaw work recognizable later. Prefer explicit labels, names, and stable session targets over anonymous UUID-only threads whenever the agent controls session creation.

Use this skill for any agent running inside OpenClaw. For non-OpenClaw agent frameworks, adapt the principles only after checking that the framework actually has equivalent concepts; do not assume `sessions_spawn`, cron `sessionTarget`, or named session persistence exist elsewhere.

This skill is an operational convention. It does not implement the separate runtime feature of renaming existing sessions in the UI/CLI.

## Pre-flight checklist

Before creating a new OpenClaw work session, check:

1. **Spawning an agent/session?**
   - Set `sessions_spawn.label`.
2. **Creating a cron job?**
   - Set a human-readable cron `name`.
3. **Will a recurring `agentTurn` job benefit from continuity?**
   - Use `sessionTarget: "session:<stable-purpose>"`.
4. **Is the job stateless?**
   - Use `sessionTarget: "isolated"` for `agentTurn` jobs.
5. **Is this an exact reminder/system event?**
   - Use `payload.kind: "systemEvent"` with `sessionTarget: "main"` and reminder-like text.
6. **Can the agent not label the current manual/dashboard/webchat session?**
   - Add a short sidecar note only if the thread is important and likely to be resumed.

Do not ask the user for a label by default. Derive one from the task. Ask only if the project identity is genuinely ambiguous.

## Label style

Treat labels, cron names, and stable session targets as visible metadata: they may appear in logs, task lists, dashboards, PRs, screenshots, notifications, or exported session records.

Use labels and stable session names that are:

- lowercase kebab-case;
- project/area first, task second;
- short but recognizable, usually 3–6 terms;
- free of secrets, API keys, phone numbers, private email addresses, personal names, customer/project codenames that are not public, or sensitive identifiers;
- neutral enough to show in a shared operations view;
- stable for recurring workflows;
- date-suffixed only for one-off batches or date-specific work.

Good:

- `cloud-api-key-security-audit`
- `runtime-storage-monitor`
- `pageindex-skills-audit`
- `youtube-transcripts-batch-20260514`
- `docs-audit-pass-20260514`

Avoid:

- `task`
- `misc`
- `new-session`
- random UUID-like labels
- labels containing secrets or private identifiers
- labels that disclose private personal, medical, legal, financial, or security-sensitive context
- date suffixes on recurring workflows that should keep one stable session

Cron `name` can be human-readable Title Case, but `session:<stable-purpose>` targets should still use kebab-case.

## `sessions_spawn` rule

When calling `sessions_spawn`, always include `label` when the tool/runtime supports it.

Preferred format:

```text
<area>-<specific-task>
```

Use a compact date suffix for separate date-specific batches:

```text
<area>-<specific-task>-YYYYMMDD
```

Examples:

```json
{
  "label": "runtime-node-reconnect-check",
  "task": "Verify that the remote node reconnects cleanly after reboot."
}
```

```json
{
  "label": "youtube-transcripts-batch-20260514",
  "task": "Archive and summarize this batch of YouTube transcripts."
}
```

## Cron rule

Always set a clear cron job `name`.

Respect runtime constraints:

- `sessionTarget: "main"` requires `payload.kind: "systemEvent"`.
- `sessionTarget: "isolated"`, `"current"`, or `"session:<stable-purpose>"` require `payload.kind: "agentTurn"`.

Decision table:

| Use case | Payload | Session target | Notes |
| --- | --- | --- | --- |
| Exact reminder | `systemEvent` | `main` | Event text should read like a reminder when fired. |
| Stateless report/background chore | `agentTurn` | `isolated` | Fresh session each run; no continuity expected. |
| Recurring workflow that benefits from memory | `agentTurn` | `session:<stable-purpose>` | Stable named session across runs. |
| Current-thread recurring work | `agentTurn` | `current` | Use rarely; only when binding to this exact session is intentional. |

Examples:

```json
{
  "name": "Daily runtime storage monitor",
  "sessionTarget": "session:runtime-storage-monitor",
  "payload": { "kind": "agentTurn" }
}
```

```json
{
  "name": "Reminder: submit weekly status update",
  "sessionTarget": "main",
  "payload": {
    "kind": "systemEvent",
    "text": "Reminder: submit the weekly status update before Friday 17:00."
  }
}
```

## Manual or existing sessions

If the agent cannot set a label for a manually-created dashboard/webchat/channel session, do not create sidecar clutter for every chat. For important long-lived work, add or update a compact sidecar note with a human-readable title. Keep sidecar notes minimal; do not copy secrets, private message contents, credentials, or sensitive identifiers into naming notes.

Suggested title format:

```text
YYYY-MM-DD — topic — surface
```

Do not manually patch `sessions.json` just to label old sessions unless the user explicitly approves that exact change and a backup is created first. Never use a labeling pass as a reason to expose, export, or summarize private transcript content beyond what is needed for the label.

## Verification

Before claiming compliance, verify at least one relevant fact:

- the `sessions_spawn` call included a non-generic `label`;
- the cron job definition has a non-generic `name`;
- recurring `agentTurn` cron jobs use the intended `sessionTarget`;
- an important manual/dashboard session has a sidecar note.
