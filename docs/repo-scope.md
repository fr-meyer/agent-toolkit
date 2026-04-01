# Repository scope

## What belongs in this repo (shared content)

The following categories are committed to git:

- **Skills** — shared agent skills
- **Cursor rules** — shared rules under the Cursor integration layout
- **Setup scripts** — `scripts/` helpers that connect OpenClaw, Cursor, and verify symlinks
- **Documentation** — including this file and `docs/setup.md`

**Core principle:** this repository is the source of truth for **shared** content only—material that should be the same for every clone and every developer.

## What does not belong (attachment state and local config)

| Category | Example | Why excluded |
| --- | --- | --- |
| Auth state | API keys, tokens, credentials | Machine- and user-specific; must never be committed |
| Runtime installs | npm packages, pip envs, tool binaries | Installed per machine; not portable as committed files |
| Machine-specific paths | Absolute paths to clones, home dirs | Differ per machine; hardcoding breaks portability |
| Per-project local state | `.cursor/rules` symlink, local overrides | Created by connect scripts; belongs to each project |
| The `~/.agent-toolkit` alias | The symlink itself | Points to a machine-specific path; cannot be shared |

## Why `~/.agent-toolkit` is not committed

The alias is a symlink to wherever this repository lives on a given machine. That path differs per machine and per developer. Committing it would either be wrong for everyone else or force machine-specific configuration into git—both conflict with the shared-content principle. You create the alias once per machine by hand (see [Setup](setup.md)); it is never tracked by git.

## The shared-content vs. attachment-state boundary (summary)

Git tracks what is **shared** across clones and teams. Each machine manages its own **attachment state** locally: symlinks, the `~/.agent-toolkit` alias, and project-specific links created by the setup scripts. That boundary keeps the repo portable and safe to collaborate on without leaking personal or machine-local configuration.
