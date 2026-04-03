# Command matrix

Use this file when you need the exact platform-to-script mapping, override names, approval checklist, or the canonical source/target path set for the `connect-openclaw` workflow.

## Script selection

| Environment | Use this connect script | Use this verify script | Notes |
| --- | --- | --- | --- |
| Windows + PowerShell 7+ (`pwsh`) | `scripts\connect-openclaw.ps1` | `scripts\verify-links.ps1` | Require `pwsh`; do not proceed from Windows PowerShell 5.1. |
| macOS / Linux | `scripts/connect-openclaw.sh` | `scripts/verify-links.sh` | Run with `bash` unless the toolkit repo docs say otherwise. |
| Git Bash on Windows | `scripts/connect-openclaw.sh` | `scripts/verify-links.sh` | Treat as Unix-like shell. |
| WSL | `scripts/connect-openclaw.sh` | `scripts/verify-links.sh` | Use Linux paths only; do not mix with Windows `%USERPROFILE%` paths. |

These script paths are relative to the **toolkit repository root**, not to this skill folder.

## Path precedence

Resolve the roots in this order:

1. explicit user-provided path
2. environment variable
3. built-in default

| Value | Env var | Default |
| --- | --- | --- |
| toolkit root | `AGENT_TOOLKIT_ROOT` | `~/.agent-toolkit` |
| OpenClaw home | `OPENCLAW_HOME` | `~/.openclaw` |
| OpenClaw scripts dir | `OPENCLAW_SCRIPTS_DIR` | `<openclaw-home>/scripts` |

## Canonical OpenClaw link set

The `connect-openclaw` workflow manages both of these links:

| Purpose | Source | Target |
| --- | --- | --- |
| OpenClaw skills | `<toolkit-root>/skills` | `<openclaw-home>/skills` |
| OpenClaw scripts | `<toolkit-root>/scripts` | `<openclaw-scripts-dir>` |

## Approval checklist

Before any write action, display all of the following in chat:

- effective toolkit root
- effective OpenClaw home
- effective OpenClaw scripts dir
- exact skills source path
- exact skills target path
- exact scripts source path
- exact scripts target path
- one line explaining how toolkit root was chosen
- one line explaining how OpenClaw home was chosen
- one line explaining how OpenClaw scripts dir was chosen
- the script variant that will be used

Then require explicit user approval before running `connect-openclaw`.

## Override name mapping

| Bash flag | PowerShell parameter |
| --- | --- |
| `--toolkit-root <path>` | `-ToolkitRoot <path>` |
| `--openclaw-home <path>` | `-OpenclawHome <path>` |
| `--openclaw-scripts-dir <path>` | `-OpenclawScriptsDir <path>` |
| `--yes` | `-Yes` |

## Verification rule

Always invoke `verify-links` with the **same** resolved override values used during the connect step.

Verification should report at least:
- `toolkit-root`
- `openclaw/skills`
- `openclaw/scripts`

## Connect behavior note

`connect-openclaw` manages both OpenClaw links in one run. Treat the outcome as per-link rather than all-or-nothing, and report each relevant success, conflict, or failure clearly.

## Conflict rule

If the resolved skills target path and scripts target path are identical, stop immediately and tell the user. Do not attempt either link.

## Fail-safe rule

If a destination already exists as a real directory or file, stop and tell the user. Do not overwrite it blindly.
