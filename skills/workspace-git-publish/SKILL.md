---
name: workspace-git-publish
description: Use this skill when the user asks Codex to sync, pull, commit, publish, or push a workspace/repository, especially when a dirty working tree or publish bridge blocks the push and Codex should partition mixed changes into thematic commits. Applies to workspace repos, memory/todo repos, OpenClaw workspace publish bridges, and other non-destructive Git publishing flows where unrelated user work must be preserved.
---

# Workspace Git Publish

## Goal

Publish a workspace without losing work or blending unrelated changes. When the tree is dirty but the user's intent is to publish, inspect and partition coherent work into thematic commits instead of stopping after the first clean-tree guard.

## Safety Rules

- Never use `git reset --hard`, `git checkout -- <path>`, `git clean`, force-push, or destructive history rewriting unless the user explicitly asks for that exact operation.
- Do not use `git stash` as a way to hide unrelated work from a publish guard. Commit publishable work by theme, or leave unsafe work in place and report it.
- Treat dirty files you did not create as user or parallel-agent work. Preserve them.
- Stage one coherent group at a time and verify the staged file list before every commit.
- If a file group is private, ambiguous, incomplete, actively changing, or not clearly safe to publish, leave it uncommitted and report the exact paths.

## Workflow

1. Inspect state:
   - `git status --short --branch`
   - `git diff --stat`
   - `git log --oneline --decorate -5`
   - `git remote -v` when push destination is unclear
2. Sync safely when requested:
   - fetch first
   - use fast-forward-only pulls when possible
   - do not rebase or merge over a dirty tree unless the user asked for that strategy
3. Identify thematic commit groups from the actual diff:
   - code and tests for one feature/fix
   - docs/runbooks/operational notes
   - todo/dashboard updates
   - daily memory traces
   - archive batches or generated durable records
   - generated temp/output files that should remain untracked
4. For each group:
   - inspect enough diff/content to confirm intent
   - stage only that group
   - run `git diff --cached --name-only`
   - run `git diff --cached --stat` for a size sanity check
   - commit with a truthful, specific message
5. Re-check `git status --short --branch`.
6. If new dirty files appear, decide whether they are a coherent follow-up group or an active-writer blocker. For active writers, wait briefly once; if changes keep appearing, stop chasing and report the live writer/group.
7. Push using the repo's appropriate mechanism:
   - normal repos: `git push`
   - repos with a local publish bridge: use that bridge
   - if the bridge refuses because the tree is dirty, repeat the partitioning pass rather than stopping immediately
8. Finish with commit hashes, push result, and any remaining uncommitted blockers.

## OpenClaw Workspace Notes

For `workspace-franck`, check local notes such as `TOOLS.md` before pushing. The workspace may use a publish bridge because GitHub write credentials live outside the container. In that setup, a clean-tree guard means "do not publish accidental partial work"; it does not mean "give up while publishable thematic changes remain."

Common publishable groups in that workspace include:

- OpenKB/PageIndex scripts, tests, and runbooks
- todo vault and dashboard updates
- daily memory traces
- YouTube transcript archive batches
- operational notes under `memory/openclaw/`

## Good Commit Messages

- `fix: harden node transfer and Mistral OCR`
- `docs: document workspace thematic publish workflow`
- `chore: update OpenClaw todo dashboard`
- `archive: add YouTube transcript batch`

Prefer several honest commits over one blended commit.
