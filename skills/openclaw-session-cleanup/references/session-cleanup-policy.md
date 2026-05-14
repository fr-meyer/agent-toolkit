# OpenClaw session cleanup policy

Use this reference when preparing a session cleanup/archive preview or reviewing a batch of candidates.

## Terms

- **Session key**: routing bucket, such as `agent:<agentId>:main` or `agent:<agentId>:dashboard:<uuid>`.
- **Session entry**: row in `~/.openclaw/agents/<agentId>/sessions/sessions.json`.
- **Transcript**: JSONL file for the current `sessionId`.
- **Archive/hide**: remove the entry from the visible session store and rename transcript files to reversible archive filenames.
- **Live mutation path**: Control UI, Gateway RPC, or CLI/API operation that uses OpenClaw's session-store writer instead of editing `sessions.json` offline.
- **Direct-store fallback**: manual/offline `sessions.json` mutation. Use only after backup and race-safety confirmation.
- **Delete**: permanent removal. Avoid unless explicitly requested and backed up.

## Candidate classification

### Usually protect

- `agent:<agentId>:main` and other configured main sessions.
- The current session handling the request.
- Sessions with active/background runs or recent tool activity.
- External chat sessions that act as future reply routes, including DMs, groups, channels, and thread-bound sessions.
- Any session the user says is important or ongoing.

### Usually safe to propose for archive

- Finished Control UI/dashboard sessions created for one-off work.
- Finished subagent sessions whose outputs were already merged into the parent task, memory, PR, report, or TODO.
- Old isolated cron run sessions after the cron run has completed and any important output has been captured elsewhere.
- Broken/stale entries whose transcript is missing, after a dry-run and backup.

### Needs review

- Sessions with unclear purpose.
- Sessions updated recently but not known to be current.
- Sessions whose transcript may contain unsaved decisions, commands, or artifacts.
- Any external chat session unless the user names it exactly and understands it may remove that conversation bucket from the visible list.

## Preservation checklist

Before archiving, check for durable coverage:

- memory daily notes or project notes;
- `memory/todo.md` or project TODO files;
- reports under `memory/`;
- commits, branches, or PRs;
- generated artifacts or transcripts intentionally saved elsewhere.

Preserve only concise unsaved deltas. Do not duplicate entire transcripts.

## Mutation checklist

Before any mutation, the preview must identify:

- exact session key(s);
- action and method;
- protected/current/active status;
- backup destination;
- transcript archive behavior;
- saved unsaved-content location, if any;
- confirmation phrase or exact key required;
- race-safety basis for any direct-store fallback, especially whether a reachable Gateway/session writer could concurrently mutate the same store;
- protected-key list passed to any fallback helper.

After mutation, verify:

- target session entry no longer appears in the session list;
- backup exists;
- archived transcripts exist or were explicitly absent;
- memory/log entry records what changed.

## Failure handling

If a supported Gateway/UI/API deletion fails, do not immediately fall back to direct store edits unless the user confirms that fallback. Explain the blocker, the race-safety concern, and the exact fallback plan.

If direct-store fallback fails after writing a backup but before completing, stop. Report the backup path and partial state. Do not run blind cleanup loops.
