---
name: openclaw-session-cleanup
description: Safely review, close, hide, archive, or delete OpenClaw sessions from session lists. Use when asked to clean up stale dashboard sessions, close a finished session, archive/delete a specific OpenClaw session key, prune unused subagent/cron sessions, or prepare a reversible session cleanup plan with backups and content-preservation checks.
---

# OpenClaw Session Cleanup

## Purpose

Close/hide finished OpenClaw sessions safely without patching OpenClaw source code or losing unique work. Treat cleanup as a guarded runtime-data operation: preview first, preserve unsaved value, back up, mutate only after explicit confirmation, then verify.

Use `openclaw-session-indexing` first when the request is only to list, title, recall, or identify candidates. Use this skill when the user wants cleanup/archive/delete/close behavior.

## Hard rules

- Do not edit OpenClaw source code, installed `/app/dist`, or product bundles.
- Do not permanently delete by default; prefer reversible archive/hide.
- Do not mutate anything before a clear preview and explicit user confirmation.
- Protect the main/current/active sessions by default.
- Do not archive durable external conversation pointers lightly: WhatsApp/Telegram/Discord/Slack DMs, groups, and thread-bound sessions may represent future reply routes.
- Save only unique unsaved deltas before archiving: decisions, TODOs, blockers, report paths, PR/commit references, or user instructions not already captured elsewhere.
- Avoid transcript dumps. Read only the minimum recent history needed to identify the session and preserve unique unsaved content.
- Prefer supported OpenClaw Gateway/UI/API mutation paths when available. Direct `sessions.json` edits are last-resort repair/fallback actions; use them only after preview, backup, confirmation, and an explicit race-safety check that a live Gateway/session writer will not concurrently mutate the same store.

## Default workflow

### 1. Identify the target

Ask for one missing decision if the target is ambiguous. Otherwise collect metadata read-only:

```bash
openclaw sessions --agent <agentId> --json --limit all
openclaw sessions --agent <agentId> --active 120 --json
```

Use first-class session tools when available. Record exact session keys. Never rely on a partial UUID if more than one key could match.

### 2. Classify protection status

Mark each candidate:

- `protected`: main session, current session, active run, or explicitly important session.
- `durable-pointer`: external chat/group/thread session that may be needed for future routing.
- `review`: content may contain unsaved decisions/TODOs or identity is unclear.
- `archive-candidate`: finished dashboard/subagent/cron/synthetic session with no unique unsaved content.
- `delete-candidate`: only when user explicitly requests stronger cleanup and reversible archive is insufficient.

Default protections:

- Protect keys ending in `:main`.
- Protect the session currently handling the request; if the user wants to close the current chat, schedule/perform cleanup only after the final reply is safely delivered.
- Protect sessions with active/background runs until completion is verified.
- Treat recent sessions conservatively unless the user names the target exactly.

### 3. Preserve unique unsaved content

Before archive/delete, check whether relevant work already exists in memory files, TODOs, reports, commits, PRs, or other durable artifacts.

If needed, inspect a small history sample only. Preserve concise deltas such as:

- unresolved TODOs or decisions;
- exact report/artifact paths;
- branch/commit/PR references;
- blockers and next actions;
- user preferences or safety constraints.

Do not copy secrets, credentials, private identifiers, or long transcript text into memory/indexes.

### 4. Preview and ask confirmation

Before mutation, show a compact preview:

```text
Target: <sessionKey>
Agent/store: <agentId> / <store path or redacted path>
Action: archive/hide from session list
Transcript handling: rename to *.deleted.<timestamp> (reversible)
Backup: sessions.json.bak-before-archive-<timestamp>
Protected checks: main/current/active = no
Race-safety: supported Gateway/API path unavailable, or direct-store fallback confirmed safe
Unsaved content: none / saved to <path>
Confirm? yes/no
```

For batches, list every target and require confirmation for the exact batch. Never sneak in extra sessions.

### 5. Execute safely

Preferred order:

1. Use a supported Control UI/Gateway session delete/archive action when available.
2. Use a supported OpenClaw CLI/API path if one exists in the running version.
3. Use the direct-store fallback only when supported live mutation is unavailable or explicitly unsuitable, and only after confirming the target store is not being concurrently written. If the Gateway is reachable and can mutate sessions, prefer the Gateway path instead of editing `sessions.json` directly.
4. As a fallback only, use `scripts/archive_session_entry.py` to back up the store, remove the exact store entry, and rename transcripts to reversible archive filenames.

Fallback helper preview:

```bash
python3 <skill-dir>/scripts/archive_session_entry.py \
  --agent <agentId> \
  --key '<sessionKey>'
```

Fallback helper apply, only after explicit confirmation:

```bash
python3 <skill-dir>/scripts/archive_session_entry.py \
  --agent <agentId> \
  --key '<sessionKey>' \
  --protect-key 'agent:<agentId>:main' \
  --protect-key '<currentOrActiveSessionKey>' \
  --apply \
  --confirm-key '<sessionKey>'
```

Use `--store <path>` instead of `--agent` for explicit offline repair. Do not use the fallback helper for current/active/main sessions.

### 6. Verify and log

After mutation:

- re-run `openclaw sessions --agent <agentId> --json --limit all` or use session tools to confirm the entry disappeared;
- confirm archive files/backups exist;
- record a concise log in the relevant memory file with target, backup path, archived transcript path(s), and verification result;
- if anything fails, stop and report the exact blocker. Do not attempt repeated destructive fixes.

## Current-session cleanup

If the user asks to close/archive the session you are replying in, do not remove it before sending the final user-visible reply. Prefer one of these concrete options:

1. Provide the exact session key and ask the user to archive it from Control UI after reading the final response.
2. Ask for explicit confirmation, send the final response, then run a one-shot post-final cleanup job that targets only that exact key.
3. If neither is available, explain the safe manual steps rather than deleting the active store row mid-turn.

Never direct-store archive the current session while the turn is still running.

## Helper resources

- `scripts/archive_session_entry.py`: fallback direct-store archive helper with dry-run default, backup, exact-key confirmation, repeatable `--protect-key` guard, main-session protection, original store-permission preservation, and reversible transcript renaming.
- `scripts/test_archive_session_entry.py`: small fixture test for the fallback helper; run when editing the helper.
- `references/session-cleanup-policy.md`: detailed safety policy and candidate classification checklist.
