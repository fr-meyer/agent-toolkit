---
name: openclaw-skill-repo-install
description: Use this skill when installing, updating, auditing, or removing an external Git/GitHub skill repository for an OpenClaw runtime after the target scope is clearly OpenClaw or `external-skill-repo-scope-router` has selected the OpenClaw adapter. Apply it for `skills.load.extraDirs`, OpenClaw-visible skill packs, single-skill repos, multi-skill repos, extraDirs ordering, duplicate skill-name resolution, and package-like updates with git or gh. Do not use it for creating new skills, generic Git operations, ClawHub installs, or explicitly Codex-only/native-agent installs.
metadata:
  openclaw:
    emoji: "📦"
    requires:
      bins: ["git"]
---

# OpenClaw Skill Repo Install

## Goal

Install and manage existing skill repositories as Git-managed packages for OpenClaw: clone the repo into a persistent repository root, add the correct skill root to `skills.load.extraDirs`, verify the loaded skill paths, and keep future updates manageable with `git` and, for GitHub repos, `gh`.

This skill is **OpenClaw-specific**: it assumes OpenClaw skill loading and `skills.load.extraDirs`. Within that scope, it is repo-, host-, and agent-neutral. Do not hardcode a specific skill repo, cloud provider, machine name, workspace, agent id, or personal path. Resolve paths from the current runtime and user intent.

It is not a universal installer for every AgentSkills-compatible or agent-platform runtime. For non-OpenClaw platforms, use this only as a conceptual reference unless a platform-specific adapter exists.

## Adapter boundary

This is the OpenClaw adapter for external skill repo installs.

If the target runtime or visibility scope is unclear, first apply `external-skill-repo-scope-router` and continue here only when its routing decision selects an OpenClaw shared/package-managed install.

Continue directly with this skill when:

- the target runtime is OpenClaw;
- the routing receipt selects `OpenClaw extraDir` or equivalent wording;
- the user is speaking from an OpenClaw-managed session and does not explicitly request another runtime;
- the user asks for shared, OpenClaw-wide, agent-visible, reusable, or extraDir-based skills;
- the request mentions a GitHub/Git skill repo, AgentSkills-compatible repo, skill pack, or multi-skill repository.

Do not install the repo into Codex `$CODEX_HOME/skills`, Claude/Cursor/Windsurf agent-private skill folders, or another private runtime-specific skill directory when this adapter is selected.

If the target scope is ambiguous, prefer OpenClaw `extraDirs` in an OpenClaw session. Ask one concise scope question only when choosing the wrong runtime would create real risk or visible configuration churn.

## Use this skill for

- installing an existing skill repo into an OpenClaw runtime;
- adding a GitHub/Git skill pack to `skills.load.extraDirs`;
- deciding whether an extraDir should be the repo root, `repo/skills`, or another contained skill root;
- auditing existing skill-repo clones and loaded paths;
- updating cloned skill repos with `git fetch`, `git pull --ff-only`, or `gh` where appropriate;
- preparing a safe branch/PR when repository documentation or shared skill metadata must change.

Do not use this skill for creating brand-new skills; use `portable-skill-authoring` for shared, portable skill authoring work. Do not use it for plain Git repository management unrelated to OpenClaw skill loading.

## Repository package model

Preferred model:

```text
<openclaw-home>/repos/<repo-slug>/        # normal Git clone
skills.load.extraDirs += <resolved-skill-root>
```

Avoid copying Git-managed `SKILL.md` files into `~/.openclaw/skills`; copied files become stale and cannot be updated, branched, or PR-managed as a package.

`~/.openclaw/skills` remains useful for local managed overrides, not for upstream GitHub-maintained skill repos.

## Inputs to resolve

Before changing anything, identify:

- target visibility scope: OpenClaw-wide, one OpenClaw agent, workspace-local, Codex-only/native-agent, or another runtime;
- whether the request is ambiguous; in an OpenClaw session, ambiguous external skill-repo installs default to OpenClaw `extraDirs` unless the user explicitly says otherwise;
- target runtime/host;
- OpenClaw home path: explicit input → `OPENCLAW_HOME` → `~/.openclaw`;
- persistent repos root: explicit input → `<openclaw-home>/repos`;
- Git remote URL or `owner/repo`;
- desired branch/ref, if not default;
- whether the repo is trusted, public, private, or unknown;
- expected skill names, if the user named them;
- config update mechanism available in this runtime.

Treat unknown trust/visibility conservatively. Inspect before loading.

## Required workflow

### 0. Confirm routing receipt

Before touching files or using any installer, confirm the install scope:

- `OpenClaw extraDir` for Git-hosted skill repos intended to be visible to OpenClaw;
- target runtime is OpenClaw;
- install model is Git-managed package plus `skills.load.extraDirs`;
- no other runtime-private install was explicitly requested.

If any of these are unclear, route through `external-skill-repo-scope-router` before proceeding.

### 1. Snapshot current state

- Check existing config without printing secrets.
- Record current `skills.load.extraDirs`.
- Check whether the target repo clone already exists.
- Check whether expected skill names already resolve from another source.
- Backup the OpenClaw config before editing it.

### 2. Clone or update the repository

Use a stable slug, normally the repository name with owner disambiguation if needed.

For GitHub repos, prefer `gh` when available and authenticated because it preserves the package-management workflow:

```bash
gh repo view OWNER/REPO
gh repo clone OWNER/REPO <repos-root>/<repo-slug>
```

Fallback for public Git repos:

```bash
git clone <remote-url> <repos-root>/<repo-slug>
```

If the directory already exists:

- require it to be a Git repo;
- verify the remote matches the requested repo;
- require a clean worktree before updating;
- use `git fetch --all --prune` and `git pull --ff-only` unless the user requested a specific branch/ref.

Do not overwrite an existing unrelated directory.

### 3. Inspect before loading

Determine the skill root by inspecting the cloned tree:

| Repo shape | extraDir to add |
| --- | --- |
| Single-skill repo with `SKILL.md` at repo root | repo root |
| Multi-skill repo with `skills/<name>/SKILL.md` | `repo/skills` |
| Multiple skill folders directly under repo root | repo root |
| Nested or unusual layout | ask or use the smallest directory that contains the intended skill folders |

Also inspect:

- `SKILL.md` frontmatter names/descriptions;
- optional `metadata.openclaw.requires` gates;
- bundled scripts for obvious unsafe behavior before making the repo visible;
- duplicate skill names already present from higher- or same-precedence roots.

If duplicate names exist, stop and ask unless the user already specified the desired precedence. `skills.load.extraDirs` is low precedence relative to workspace, agent, managed, and bundled skills, so always verify the final source path after loading.

### 4. Update `skills.load.extraDirs`

Use the runtime's first-class config mechanism when available. If no config tool is available, edit the config file only after backing it up and preserving all existing keys.

Rules:

- append or insert the resolved skill root without replacing unrelated entries;
- preserve intentional ordering;
- use absolute paths for persistent runtime installs;
- do not add both a repo root and its nested `skills/` directory unless there is a documented reason;
- do not add duplicate path entries;
- avoid symlink-only workflows for Git-managed skill repos unless the user explicitly chose that pattern.

### 5. Reload and verify

After config change, use the least disruptive refresh available:

1. rely on skill watcher / next-turn refresh when sufficient;
2. use a config reload command/tool if available;
3. restart the Gateway only when required by the runtime.

Verification checklist:

- `openclaw skills check` succeeds;
- expected skills are eligible/visible for the intended agent;
- `openclaw skills info <skill-name>` points to the cloned repo path;
- the install did not land only in an agent-private skill folder unless that was explicitly requested;
- the expected skill source matches the target scope: OpenClaw installs should resolve from the configured extraDir clone path, not from Codex `$CODEX_HOME/skills` or another private runtime cache;
- duplicate-name resolution matches the user's intended source;
- existing unrelated extraDirs still load;
- no secrets, transient URLs, or private tokens were printed in logs or chat.

## Branch and PR hygiene for repo changes

Installing a repo into OpenClaw config is not the same as editing a shared skill repository. If the task also requires changing a shared skill repo, docs, or install guidance:

- fetch the target base branch first;
- create a dedicated feature branch from the current upstream base head;
- never commit directly on `dev`, `main`, or a shared integration branch;
- keep one logical change per branch/PR;
- run a PR preflight on both branch diff and PR title/body before publishing.

Example:

```bash
git fetch origin dev
git checkout -B feat/<purpose> origin/dev
```

Use `gh pr create` only after validation and public-safety checks pass.

## Removal or disabling

Removing a skill repo from OpenClaw requires explicit user approval. Prefer reversible steps:

1. remove or disable the extraDir entry;
2. reload/restart and verify the skill is no longer visible or resolves from the intended fallback;
3. keep the repo clone unless the user explicitly asks to delete it;
4. if deletion is approved, use a recoverable trash/archive path when available.

## Output expectations

Report:

- target visibility scope chosen and why;
- repo remote and local clone path;
- detected repo shape and chosen extraDir;
- config backup path or why no file backup was needed;
- previous and final `skills.load.extraDirs` entries, summarized without secrets;
- skills added/updated and their resolved source paths;
- duplicate-name decisions;
- validation commands/results;
- whether any agent-private install path was skipped, left untouched, or intentionally used;
- whether a reload/restart was needed.
