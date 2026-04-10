---
name: git-repo-sync
description: Use this skill when the user needs to inspect or safely reconcile a single local Git repository with its tracked upstream, especially for dry-run sync planning, ahead/behind checks, commit-draft generation, explicitly authorized fetch/pull/rebase/push workflows, or opt-in decomposition of a mixed local change set into multiple coherent commits before sync. Apply it when requests involve repo synchronization, drift detection, safe sync planning, or routine Git reconciliation. Do not use it for PR review, repository bootstrap, CI/CD authoring, branch strategy design, destructive recovery, multi-repo orchestration, or human merge-conflict resolution.
---

# Git Repo Sync

## Goal

Help the agent safely inspect, plan, and optionally execute synchronization of **one local Git repository** with its tracked upstream, including an opt-in path for splitting a mixed local change set into multiple coherent commits before sync.

This skill is designed to be:
- provider-agnostic
- dry-run-first
- safe by default
- reusable from cron, manual agent turns, CI callers, or other orchestration layers

The skill owns **repo-sync logic only**.
It does **not** own scheduling, CI workflow design, Git hosting APIs, or multi-repo orchestration.

## Default approach

- **Default mode:** `inspect-only`
- **Default behavior:** no network actions, no write actions
- **Default commit strategy:** `single-commit`
- **Preferred sequence:** inspect -> classify state -> choose safest next action -> execute only if explicitly allowed
- **Avoid:** implicit writes, implicit pulls, implicit rebases, branch switching, destructive cleanup, or guessing missing configuration

If the caller has not clearly authorized execution:
- do not fetch
- do not pull
- do not rebase
- do not commit
- do not push

## Use this skill for

- checking whether a local repo is ahead or behind its upstream
- determining whether a repo is safe to sync
- preparing a dry-run sync plan
- drafting a commit message for current local changes
- safely reconciling one repo with its upstream when permissions are explicit
- splitting a mixed local change set into multiple coherent commits when that behavior is explicitly requested
- powering a scheduled or recurring sync workflow from another system

## Do not use this skill for

- PR review or code review
- GitHub-specific API tasks
- repo cloning or first-time bootstrap
- CI/CD or GitHub Actions authoring
- branch strategy design
- merge-conflict judgment/resolution
- destructive recovery (`reset --hard`, `clean -fd`, force push)
- multi-repo batch sync or deployment orchestration

## Required inputs

Gather as many of these as the task supports:

- `repo_path`
- `mode`, one of:
  - `inspect-only`
  - `dry-run-sync-plan`
  - `commit-draft`
  - `execute-approved`
- optional `commit_strategy`, one of:
  - `single-commit`
  - `split-by-scope`
- permission flags:
  - `allow_fetch`
  - `allow_pull`
  - `allow_rebase`
  - `allow_commit`
  - `allow_push`
- optional execution limits:
  - `max_auto_commits`
  - `include_untracked`
  - `stop_on_ambiguous_remainder`
- optional branch constraint
- optional upstream constraint
- optional remote constraint
- any policy limits such as:
  - max diff size
  - forbidden paths
  - no push
  - no commit
  - no rebase
  - no untracked-file tolerance
- optional public safety and docs-gate inputs:
  - `repo_visibility_context`, one of: `public`, `private`, `unknown`, `public-intended`
  - `enforce_public_red_list_gate`, boolean
  - `enable_docs_readiness_gate`, boolean
  - `auto_remediate_public_red_list`, boolean
  - `auto_update_docs_before_commit`, boolean

If permissions are unclear, assume:

```yaml
mode: inspect-only
allow_fetch: false
allow_pull: false
allow_rebase: false
allow_commit: false
allow_push: false
commit_strategy: single-commit
include_untracked: false
stop_on_ambiguous_remainder: true
```

## Active sync target determination

This skill operates on **one active local branch** and its **tracked upstream** only.

Determine the active sync target using these rules, in order:

1. Use the **currently checked-out local branch** as the only candidate local branch.
2. Use that branch's **configured tracked upstream** as the only candidate upstream target.
3. If the current branch has **no configured upstream**, return `needs-config`.
4. If `HEAD` is detached, do not sync; return `blocked` or `needs-config` with a clear reason.
5. If the caller supplied expected branch, upstream, or remote constraints and the detected values do not match them, return `needs-config` or `blocked`.
6. Do **not** switch branches automatically.
7. Do **not** choose a different local branch just because it has a cleaner or more convenient upstream.
8. Do **not** attempt to sync multiple branches in one run.

If the active branch/upstream relationship is missing, inconsistent, or ambiguous, stop and report the problem rather than guessing.

## Status vocabulary

Use exactly one primary `status` value from this set:

- `no-op`
- `clean-but-untracked`
- `local-changes-detected`
- `pull-needed`
- `push-needed`
- `diverged`
- `blocked`
- `needs-config`
- `conflict`

### Status meanings

- `no-op`
  Working tree is clean, upstream is configured, and no sync action is needed.

- `clean-but-untracked`
  Tracked files are clean, but untracked files exist and may affect sync policy.

- `local-changes-detected`
  Local staged or unstaged changes exist, and sync would require an explicit commit/stash policy before proceeding.

- `pull-needed`
  Upstream is ahead and local state is otherwise safe enough to plan or perform a pull.

- `push-needed`
  Local branch is ahead of upstream and working tree is otherwise clean enough to plan or perform a push.

- `diverged`
  Local and upstream both have unique commits. Do not reconcile automatically.

- `blocked`
  Safe sync is blocked by an in-progress Git operation, a caller policy, auth limitations, missing Git CLI, or another hard stop.

- `needs-config`
  Required repo/upstream/branch information is missing or does not match caller constraints.

- `conflict`
  An actual merge/rebase/cherry-pick conflict state is present.

### Status precedence

If more than one status appears plausible, use this precedence order:

1. `conflict`
2. `blocked`
3. `needs-config`
4. `diverged`
5. `local-changes-detected`
6. `pull-needed`
7. `push-needed`
8. `clean-but-untracked`
9. `no-op`

Always report the **highest-priority governing state**.

## Planned action vocabulary

Use one of these values for `planned_action`:

- `do-nothing`
- `report-only`
- `draft-commit-message`
- `fetch-and-reassess`
- `pull`
- `pull --rebase`
- `commit-then-sync`
- `split-commit-then-sync`
- `push`
- `stop-and-escalate`

Prefer the **least risky valid action**.

## Workflow

### 1. Lock the operating policy

Before doing anything, determine and state:

- repo path
- requested mode
- commit strategy
- whether network actions are allowed
- whether write actions are allowed
- whether commit creation is allowed
- whether push is allowed
- any caller-specified branch/upstream/remote constraints
- any safety or policy limits

If the caller did not explicitly allow execution, remain in `inspect-only` or `dry-run-sync-plan`.

### 2. Inspect repository state

Verify and inspect the following:

- Git CLI is available and callable in PATH
- repo path exists
- repo path is inside a Git repository
- current branch
- tracked upstream branch, if any
- active remote URL, if any
- whether merge, rebase, cherry-pick, or bisect is already in progress
- working tree state
- staged changes
- unstaged changes
- untracked files
- ahead/behind state relative to upstream, when available
- whether the branch/upstream/remote satisfies caller constraints

Treat the currently checked-out branch and its tracked upstream as the only valid sync target for this run unless the caller explicitly constrains the target more narrowly.

If Git is unavailable, return `blocked` with a clear reason and do not continue.
Do not guess missing upstream configuration.
Do not assume `origin`.
Do not assume `main` or `master`.

### 2.5 Public-repo safety and documentation gates

Before selecting commit or push actions, decide which delegated skills are required:

- If this run may commit or push to a public repository, or a repository intended to become public, activate `public-repo-red-list-audit` before any commit or push action.
- Use the available change scope (staged, unstaged, and approved untracked files) and the best available visibility context (`public`, `private`, `unknown`, `public-intended`).
- If `public-repo-red-list-audit` reports blocker findings, activate `public-repo-red-list-remediation` before committing.
- After remediation, re-run `public-repo-red-list-audit`. If blockers still remain and no concrete remediation is available, then set:
  - `status: blocked`
  - `planned_action: stop-and-escalate`
  and do not commit or push in this run.
- If the changed work creates clear documentation drift, activate `repo-documentation-drift-fix` before commit.
- Activate `repo-documentation-audit` only when the caller explicitly requests broader publishability or docs-readiness evaluation.
- Treat broad documentation-readiness findings as advisory unless the caller explicitly asks to gate sync on documentation readiness.

### 3. Classify the governing sync state

Assign exactly one primary `status` using the required vocabulary and precedence rules.

When deciding, follow these rules:

- if conflict markers or in-progress rebase/merge conflict state exist -> `conflict`
- if merge/rebase/cherry-pick/bisect is in progress and safe sync should not continue -> `blocked`
- if required upstream/remote/branch config is missing or mismatched -> `needs-config`
- if both local and remote have unique commits -> `diverged`
- if staged or unstaged local edits exist -> `local-changes-detected`
- if upstream is ahead and local state is otherwise safe -> `pull-needed`
- if local branch is ahead and tree is otherwise clean -> `push-needed`
- if tree is clean except for untracked files -> `clean-but-untracked`
- otherwise -> `no-op`

### 4. Choose the safest next action

Choose the narrowest safe `planned_action`.

Guidance:

- `no-op` -> usually `do-nothing`
- `clean-but-untracked` -> usually `report-only`
- `local-changes-detected` with commit not allowed -> `draft-commit-message` or `report-only`
- `local-changes-detected` with `allow_commit: true` and `commit_strategy: single-commit` -> `commit-then-sync` only when one truthful single-purpose commit clearly fits the visible change set
- `local-changes-detected` with `allow_commit: true` and `commit_strategy: split-by-scope` -> `split-commit-then-sync` only when the change set can be decomposed into coherent commit groups without guessing
- `pull-needed` with fetch/pull allowed -> `pull` or `pull --rebase`
- `push-needed` with push allowed -> `push`
- `diverged` -> `stop-and-escalate`
- `blocked` -> `stop-and-escalate`
- `needs-config` -> `stop-and-escalate`
- `conflict` -> `stop-and-escalate`

Never choose a riskier action when a safer one would satisfy the request.

### 5. Draft commit metadata or a multi-commit plan when appropriate

If local changes exist and the caller asked for `commit-draft` or a sync plan that includes commit preparation:

- produce one commit title draft
- produce one short commit body draft

If the caller requested `commit_strategy: split-by-scope`, activate `changeset-commit-partitioner` to produce a brief commit plan that groups changed files by commit intent and drafts grounded commit metadata.

The commit draft should follow **Conventional Commits** style.

#### Commit title draft rules

Format:

```text
type: short summary
```

Rules:
- choose the narrowest fitting type from:
  - `feat`
  - `fix`
  - `docs`
  - `refactor`
  - `chore`
  - `test`
  - `build`
  - `ci`
- keep the title short, specific, and grounded in the visible changes
- do not mention work that is not supported by repo evidence
- do not include trailing punctuation

#### Commit body draft rules

- keep the body short and readable
- explain the main changes visible in the repo
- use either:
  - one short paragraph, or
  - 1-3 short bullet lines
- do not invent motivation, impact, or hidden context that is not supported by visible evidence

If commit creation is **not** explicitly allowed:
- do not stage
- do not commit
- do not stash
- only draft the message

If no meaningful commit draft is needed, set draft fields to `none`.

#### General classification rules for `split-by-scope`

When `commit_strategy: split-by-scope` is explicitly requested, activate `changeset-commit-partitioner`.

That skill should own:
- grouping by visible diff intent
- checking cross-file coherence
- drafting grounded Conventional Commit metadata
- identifying ambiguous remainder that should not be forced into a commit

Use path names, extensions, and directories only as weak hints. Do **not** hardcode repo-specific buckets in this skill.

### 5.5 Automatic remediation and docs updates before commit

When a pending commit or push is in scope:

- If `public-repo-red-list-audit` finds blocker content, activate `public-repo-red-list-remediation` before staging or committing.
- Re-run the red-list audit after each remediation pass. Proceed only when blocker findings are cleared, or stop and report if no concrete remediation can be determined.
- If the changed behavior creates clear local docs drift, activate `repo-documentation-drift-fix` before commit.
- Keep documentation updates truthful, local, and tied directly to the changed behavior.
- If documentation needs are broad or ambiguous and no concrete local update can be determined, stop and report rather than inventing unsupported documentation.

### 6. Execute only if explicitly approved

Execution is allowed only in `execute-approved` mode and only for verbs explicitly permitted by flags.

#### Allowed action rules

- `allow_fetch: true` permits fetch
- `allow_pull: true` permits pull
- `allow_rebase: true` permits pull with rebase
- `allow_commit: true` permits staging/commit creation
- `allow_push: true` permits push
- `commit_strategy: split-by-scope` permits **multiple** commits only when `allow_commit: true` is also set

Do not infer permission for one action from another.

Examples:
- `allow_pull: true` does **not** imply `allow_rebase: true`
- `allow_commit: true` does **not** imply `allow_push: true`
- `commit_strategy: split-by-scope` does **not** imply `include_untracked: true`

#### Execution guardrails

Stop immediately if:

- the repo enters conflict state
- branch/upstream/remote fails caller constraints
- a merge/rebase/cherry-pick is already in progress
- the required auth for network actions is missing
- the diff exceeds caller policy
- suspicious or forbidden files remain present in the pending commit after required remediation attempts
- the repo is diverged and manual judgment is required

#### Multi-commit execution loop

When all of the following are true:

- `mode: execute-approved`
- `allow_commit: true`
- `commit_strategy: split-by-scope`

the agent may execute this loop:

1. Inspect the full change set.
2. Partition it into candidate commit groups using the general classification rules above.
3. Reject any candidate group that would require speculative intent or a misleading commit message.
4. Stage only one coherent group.
5. Draft a grounded Conventional Commit title/body for that group.
6. Commit that staged group.
7. Reassess the remaining changes from scratch.
8. Repeat until no safe groups remain.

Rules for this loop:

- Default to tracked changes only. Include untracked files only when `include_untracked: true` was explicitly allowed.
- Keep each commit semantically narrow.
- Do not mix unrelated changes merely to empty the working tree.
- Prefer more small truthful commits over fewer blended commits.
- Respect `max_auto_commits` when provided.
- If `stop_on_ambiguous_remainder: true`, stop when the remainder cannot be grouped safely.
- Before finishing, account for every originally changed file as one of:
  - committed
  - intentionally left uncommitted by caller policy
  - blocked as ambiguous or risky

The goal is full accounting, not forced commitment at any cost.

### 7. Validate before finishing

Before finalizing, verify:

- reported branch is correct
- reported upstream is correct, if one exists
- remote URL is correct, if relevant
- no hidden write action occurred outside policy
- no destructive Git command was used
- final repo state matches the reported outcome
- no public red-list blocker remains in the pending commit scope
- directly implied local documentation updates were included, or inability to produce them is clearly reported
- `executed_actions` includes only actions actually performed
- every originally changed file is accounted for in either executed commits or the reported remainder/blocker

## Output format

Return a concise structured report like this:

```yaml
repo_path:
mode:
status:
planned_action:
current_branch:
upstream:
remote_url:
in_progress_operation:
working_tree_summary:
untracked_files:
ahead_by:
behind_by:
blocked_reason:
policy_summary:
executed_actions:
commit_title_draft:
commit_body_draft:
commit_sequence:
remaining_changes_summary:
notes:
```

### Output rules

- always include `status`
- always include `planned_action`
- if no upstream exists, set `upstream: none`
- if no remote URL is available, set `remote_url: none`
- if no in-progress Git operation exists, set `in_progress_operation: none`
- if no commit draft is needed, set:
  - `commit_title_draft: none`
  - `commit_body_draft: none`
- if no multi-commit sequence is planned or executed, set `commit_sequence: []`
- if no changes remain, set `remaining_changes_summary: none`
- if nothing was executed, set `executed_actions: []`
- keep `notes` brief and factual

## Gotchas

- Do not assume the branch is `main` or `master`; detect it.
- Do not assume the remote is `origin`; detect the tracked upstream.
- Do not guess missing upstream configuration.
- Do not switch branches to "make sync work".
- Do not auto-stash unless the caller explicitly asked for that policy.
- Do not use destructive Git commands.
- A diverged branch is not the same as `pull-needed`.
- Untracked files do not mean the repo is clean for sync purposes.
- Missing auth for network actions is a blocker, not a reason to improvise.
- Blocker findings from `public-repo-red-list-audit` require remediation before commit/push, not just passive reporting.
- Prefer temporary breakage over committing dangerous red-list content.
- In `split-by-scope` mode, use `changeset-commit-partitioner` rather than reinventing commit grouping inline.
- "All files accounted for" does not mean "force every leftover file into some commit."
- This skill handles **one repo at a time**.

## Resources

Read only when needed:

- `references/eval-prompts.json` - use when refining trigger precision or checking false positives / false negatives

## Portability notes

- Use plain Git concepts that work across hosting providers.
- Do not hardcode GitHub, GitLab, Bitbucket, or OpenClaw-specific behavior into the core procedure.
- Scheduling systems such as cron, CI, or agent orchestrators should call this skill; they are not part of the skill itself.
- Keep provider-specific APIs out of scope unless the user explicitly asks for a different skill.
- Prefer inspection and plain Git CLI reasoning over environment-specific automation assumptions.

## Examples of appropriate requests

- "Check whether this repo is ahead or behind its upstream."
- "Prepare a safe dry-run sync plan for this repository."
- "Draft a commit message for the current local changes."
- "Sync this repo only if pull, rebase, and push are explicitly allowed and safe."
- "Inspect this repo for a cron-driven sync workflow."
- "Split this mixed local change set into multiple neat commits, then sync if safe."

## Examples of out-of-scope requests

- "Review my pull request comments."
- "Create a GitHub Actions deployment workflow."
- "Clone this repo and install dependencies."
- "Resolve this merge conflict and choose the right code."
- "Design a branching strategy for my team."
- "Sync these 20 repos across all servers."

## Never do this

- Never force push.
- Never run `git reset --hard` automatically.
- Never run `git clean -fd` automatically.
- Never switch branches without explicit instruction.
- Never guess a missing upstream and pretend it is correct.
- Never hide divergence or conflict behind vague wording.
- Never commit or push unless explicitly allowed.
- Never treat provider-specific conventions as universal Git behavior.
- Never expand from one repo to many repos inside this skill.
