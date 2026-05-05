# Repository scope

## What belongs in this repo (shared content)

The following categories are committed to git:

- **Skills** — shared agent skills under `skills/`
- **Skill-local runtime resources** — each skill's own `scripts/`, `references/`, and `assets/` when needed
- **Workflow assets** — source workflow templates and manifests under `templates/`
- **Workflow and repository helper scripts** — repo/CI/distribution helpers under `scripts/`
- **Cursor rules** — shared rules under the Cursor integration layout
- **Documentation** — including this file and `docs/setup.md`

**Core principle:** this repository is the source of truth for **shared** content only—material that should be the same for every clone and every developer.

## What does not belong (attachment state and local config)

| Category | Example | Why excluded |
| --- | --- | --- |
| Auth state | API keys, tokens, credentials | Machine- and user-specific; must never be committed |
| Runtime installs | npm packages, pip envs, tool binaries | Installed per machine; not portable as committed files |
| Machine-specific paths | Absolute paths to clones, home dirs | Differ per machine; hardcoding breaks portability |
| OpenClaw local config | `skills.load.extraDirs`, model keys, node routes | Belongs to each OpenClaw installation, not the shared repo |
| OpenClaw attachment state | Legacy `~/.openclaw/skills` or `~/.openclaw/scripts` symlinks | Obsolete local wiring; OpenClaw should use explicit config |
| Per-project local state | `.cursor/rules` symlink, local overrides | Created per project; belongs to each project checkout |
| The `~/.agent-toolkit` alias | The symlink itself | Points to a machine-specific path; cannot be shared |

## Why `~/.agent-toolkit` is not committed

The alias is a symlink to wherever this repository lives on a given machine. That path differs per machine and per developer. Committing it would either be wrong for everyone else or force machine-specific configuration into git—both conflict with the shared-content principle. You may create the alias locally for convenience, but it is never tracked by git.

## Script placement rule

Runtime scripts required by a skill belong inside that skill's own `scripts/` directory. That keeps skills self-contained when copied, packaged, or installed independently.

Repo-level `scripts/` are for repository automation, CI workflows, distribution/materialization helpers, and integration setup that is intentionally broader than one skill.

## The shared-content vs. attachment-state boundary (summary)

Git tracks what is **shared** across clones and teams. Each machine manages its own **attachment state** locally: OpenClaw config, optional aliases, and project-specific links created by setup scripts. That boundary keeps the repo portable and safe to collaborate on without leaking personal or machine-local configuration.
