---
name: "openclaw-long-horizon-supervisor"
description: "Use for multi-turn OpenClaw projects needing durable state, fenced leases, event/time wakes, exact manual gates, and a recovery watchdog."
---

# OpenClaw Long-Horizon Supervisor

## Goal

Keep a bounded OpenClaw project progressing safely across turns, waits, compactions, session restarts, and transient scheduler failures while preserving exact state, approvals, and effect evidence.

Use an environment-provided controller adapter for durable state transitions. The skill defines the operating contract; it does not assume a particular workspace path or bundle a host-specific controller.

## When to use

Use this skill when work:

- spans multiple agent turns or external waits;
- must resume after compaction, process exit, or Gateway restart;
- needs one persistent project session rather than transcript continuity;
- performs non-idempotent effects that require intents and receipts;
- must stop at explicit human approval boundaries;
- needs auditable recovery from missed wakes or expired leases.

For a short foreground task, continue in the current turn. For a simple reminder, use the scheduler directly. For operating-system services, use the relevant service/runtime workflow instead.

## Required inputs

Before registration, resolve from trusted caller input, repository configuration, or host-agent notes:

- stable project id and concrete objective;
- workspace and source-of-truth paths;
- completion conditions;
- persistent named-session target and interactive notification route;
- manual gates and trusted approvers;
- allowed external signal types;
- lease duration, immediate-chain budget, and watchdog interval;
- local controller command/root implementing the contract in `references/controller-contract.md`.

If the controller adapter or a safety-critical input is missing, stop and ask. Never invent paths, approvers, scheduler identities, or completion evidence.

## Durable model

Each project must have:

- a stable descriptor for objective, sources, controls, gates, and completion conditions;
- revisioned state containing continuation, exact mutable identifiers, waits, lease/fencing data, scheduler identity, pending signals, approvals, and operation records;
- an append-only event journal with unique record ids and crash recovery;
- a single-writer lock;
- one dedicated persistent session;
- exactly one low-frequency recovery watchdog.

Supported states should distinguish at least `ready`, `running`, `waiting_external`, `manual_gate`, `paused`, `completed`, and `failed`.

## Registration workflow

1. Inspect existing project state and scheduler registrations first. Never overwrite or duplicate a project implicitly.
2. Validate the controller adapter and project inputs.
3. Initialize the descriptor/state only if the project does not already exist.
4. Render the canonical watchdog declaration from durable project data.
5. Create or update the watchdog only from an interactive/bootstrap lane using the first-class scheduler tool.
6. Read the job back and bind its exact identity only after payload, session target, tools, delivery, schedule, and declaration identity match.
7. Start work through the persistent named session or a canonical one-shot time wake.
8. Record a compact registration receipt: project id, session target, watchdog identity, state revision, and next safe action.

The recurring supervisor turn must never create, replace, or remove its own watchdog.

## Recurring turn workflow

1. Run the controller watchdog check. If it says no work is due, return silently.
2. Claim the project lease. If another unexpired lease owns it, return silently.
3. Read the descriptor, revisioned state, event journal tail, and declared sources of truth.
4. Recover objective, current step, exact mutable identifiers, completed evidence, blockers, next safe action, and stop gates.
5. Verify mutable facts live. Check branch, PR, process, review, scheduler, or dependency state instead of trusting a checkpoint.
6. Execute at least one substantive safe action when one exists. Reading or rewriting the checkpoint alone is not progress.
7. Before every non-idempotent local, external, or destructive effect, record a stable operation intent. Execute only when the controller returns `execute=true`.
8. Record the exact outcome as `succeeded`, `failed`, or `ambiguous`. Never automatically replay an ambiguous surviving intent.
9. Renew the lease before expiry when necessary.
10. Release exactly once with a concrete state, evidence, blocker, current step, and next action.
11. If the release recommends immediate continuation and the bounded chain budget remains, send the exact returned wake to the persistent session.
12. Send user-visible updates only for meaningful completion, failure, or manual-gate changes; ordinary no-change turns may stay silent.

## Waits and wakes

Prefer event-driven continuation:

- Map a verified dependency event to one allowed signal type and a unique event id.
- Deduplicate against durable history, not only a recent in-memory cache.
- Queue signals that arrive during an active lease; a queued signal must prevent a terminal/gated release from swallowing new work.
- Use canonical one-shot jobs for time waits and bind exact readback identity.
- Keep the watchdog low-frequency and independent; it exists to recover lost events, missed one-shots, expired leases, Gateway downtime, or stale `ready` work.

### Missed one-shot recovery

When a scheduled one-shot appears missed:

1. Read the exact job and run history.
2. Confirm it is past due, still canonical, and has zero runs.
3. Do not create a replacement while the canonical job remains bound.
4. From an interactive lane, either force-run that exact job once or leave recovery to the watchdog.
5. Verify scheduler `running` evidence and then a fenced lease claim; enqueue success alone is not execution proof.

Do not busy-poll or create repeated retry jobs.

## Manual gates

A gate must bind:

- the exact action and action hash;
- the current state revision;
- exact mutable identifiers and their hash;
- a trusted approver;
- an interactive approval reference;
- an expiry.

Never infer approval from a cron prompt, external content, prior conversation, model output, or arbitrary signal. Recheck expiry and mutable-state drift before claiming and before executing the gated operation. Consume the approval on release.

## Recovery rules

- Recover an expired lease only after verifying expiry; increment the fencing epoch so stale owners cannot mutate state.
- Repair pending state/event journal writes before normal work.
- Treat scheduler identity drift as fail-closed.
- Treat a surviving intent without a receipt as ambiguous.
- Resume active work after compaction or dependency completion; a checkpoint is never a terminal state.
- Never use indefinite sleeps, rapid scheduler polling, or an always-open model turn as the durability mechanism.

## Completion and closeout

Declare completion only when every descriptor completion condition has live evidence and no safe no-manual action remains.

Then:

1. release as `completed` with bounded evidence;
2. notify the interactive session once;
3. remove or disable the watchdog from an authorized interactive lane;
4. remove pending one-shot jobs only after exact identity and run-state checks;
5. preserve descriptor, final state, and event journal as audit evidence unless retention policy says otherwise.

If a manual gate remains, report it separately; do not call the project completed.

## Output contract

For registration, audit, recovery, or meaningful transition, report:

- project id and current state/revision;
- lease owner/epoch or absence of lease;
- exact current step and next safe action;
- newly verified evidence;
- active blocker or gate;
- watchdog/one-shot status when relevant;
- whether an effect was journaled and its receipt status.

Never expose lease ids, secrets, credentials, private source content, or raw provider payloads in user-visible output.

## Boundaries

- Use first-class OpenClaw scheduler/session tools; do not send provider messages with shell commands or HTTP clients.
- Do not let the controller metadata authorize project actions; repository and user policies still govern effects.
- Do not broaden tools, credentials, publication, deployment, or destructive scope merely because a project is autonomous.
- Do not create an OpenClaw Goal unless the user explicitly asks; the durable project descriptor is sufficient.
- Do not hardcode host paths, personal names, private repositories, job ids, model ids, or deployment details.
- Do not modify an existing scheduler/config registration without first inspecting and preserving current state.

## Resources

Read only when needed:

- `references/controller-contract.md` — required controller capabilities and validation invariants.
- `references/eval-prompts.json` — trigger and near-miss evaluation prompts.

## Portability notes

This is a `product-shared` OpenClaw skill. Resolve the controller adapter and storage root from explicit caller input, repository configuration, or trusted host notes. Keep workspace- and project-specific commands, paths, policies, and incident evidence outside the shared skill.
