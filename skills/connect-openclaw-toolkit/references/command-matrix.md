# Command matrix

Use this file when you need the exact platform-to-script mapping, override names, or approval checklist for the `connect-openclaw` workflow.

## Script selection

| Environment | Use this connect script | Use this verify script | Notes |
| --- | --- | --- | --- |
| Windows + PowerShell 7+ (`pwsh`) | `scripts\connect-openclaw.ps1` | `scripts\verify-links.ps1` | Require `pwsh`; do not proceed from Windows PowerShell 5.1. |
| macOS / Linux | `scripts/connect-openclaw.sh` | `scripts/verify-links.sh` | Run with `bash` unless executable docs in the repo say otherwise. |
| Git Bash on Windows | `scripts/connect-openclaw.sh` | `scripts/verify-links.sh` | Treat as Unix-like shell. |
| WSL | `scripts/connect-openclaw.sh` | `scripts/verify-links.sh` | Use Linux paths; do not mix with Windows `%USERPROFILE%` paths. |

## Path precedence

Resolve the roots in this order:

1. explicit user-provided path
2. environment variable
3. built-in default

| Root | Env var | Default |
| --- | --- | --- |
| toolkit root | `AGENT_TOOLKIT_ROOT` | `~/.agent-toolkit` |
| OpenClaw home | `OPENCLAW_HOME` | `~/.openclaw` |

## Approval checklist

Before any write action, display all of the following in chat:

- effective toolkit root
- effective OpenClaw home
- exact source path: `<toolkit-root>/skills`
- exact target path: `<openclaw-home>/skills`
- one line explaining how toolkit root was chosen
- one line explaining how OpenClaw home was chosen
- the script variant that will be used

Then require explicit user approval before running `connect-openclaw`.

## Override name mapping

| Bash flag | PowerShell parameter |
| --- | --- |
| `--toolkit-root <path>` | `-ToolkitRoot <path>` |
| `--openclaw-home <path>` | `-OpenclawHome <path>` |
| `--yes` | `-Yes` |

## Verification rule

Always invoke `verify-links` with the **same** resolved override values used during the connect step.

## Fail-safe rule

If the target already exists as a real directory or file, stop and tell the user. Do not overwrite it blindly.
