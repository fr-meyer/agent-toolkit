---
name: connect-openclaw-toolkit
description: Use this skill when the user needs to connect a shared toolkit repository into OpenClaw by creating, verifying, or repairing the OpenClaw `skills` and `scripts` symlinks using the toolkit repo's `connect-openclaw` and `verify-links` scripts. Apply it for requests about wiring a toolkit to OpenClaw, re-running `connect-openclaw`, fixing a broken `.openclaw/skills` or `.openclaw/scripts` link for this workflow, or confirming the resolved source and target paths before linking. Do not use it for Cursor-only setup, unrelated symlink troubleshooting, or editing the toolkit repo's setup scripts.
compatibility: Requires a toolkit repository with the expected `scripts/connect-openclaw.*` and `scripts/verify-links.*` files plus the `skills/` and `scripts/` directories; Windows requires PowerShell 7+ for the `.ps1` path, otherwise use bash in Unix-like environments.
---

# Connect OpenClaw Toolkit

## Goal

Safely connect a toolkit repository into OpenClaw by resolving the correct source and target paths, selecting the correct platform-specific script from the toolkit repository, obtaining explicit approval before changes, creating the required OpenClaw `skills` and `scripts` symlinks, and then verifying the result with matching overrides.

## Default workflow

1. Confirm the request is specifically about connecting a toolkit repo into OpenClaw or verifying that connection.
2. Determine the runtime environment and choose the correct script family.
3. Resolve `toolkit-root`, `openclaw-home`, and `openclaw-scripts-dir` using documented precedence rules.
4. Compute and display the exact `skills` and `scripts` source and target paths before any write action.
5. If present, read `<toolkit-root>/docs/setup.md` and treat it as the current behavior source of truth.
6. Require explicit user approval for the resolved paths.
7. After approval, run the appropriate `connect-openclaw` script from the toolkit repository.
8. Immediately run the matching `verify-links` script from the toolkit repository with the same overrides.
9. Report the exact outcome, including per-link status and any remediation needed.

## Scope boundaries

Use this skill for:
- Linking a toolkit repo's `skills` and `scripts` directories into OpenClaw
- Re-running `connect-openclaw` safely after path review
- Verifying or repairing a broken `.openclaw/skills` or `.openclaw/scripts` link for this toolkit workflow
- Explaining which script variant to use on Windows vs Unix-like environments
- Confirming the resolved OpenClaw link plan before any change is made

Do not use this skill for:
- `connect-cursor` or `.cursor/rules` setup by itself
- Generic symlink debugging unrelated to this toolkit repo workflow
- Editing the toolkit repo's setup scripts or redesigning their behavior
- Blindly running link scripts before resolving and showing the paths

## Important assumption

The `connect-openclaw` and `verify-links` scripts referenced by this skill are expected to live in the **toolkit repository being connected**, not inside this skill folder.

When this skill refers to paths such as `scripts/connect-openclaw.sh` or `scripts/verify-links.ps1`, treat them as paths inside the toolkit repository root.

## Procedure

### 1) Identify platform and shell

Choose the script family by environment:

- **Windows + PowerShell 7+ (`pwsh`)**
  - Use `scripts/connect-openclaw.ps1`
  - Use `scripts/verify-links.ps1`
- **Windows PowerShell 5.1**
  - Stop and tell the user the PowerShell path requires **PowerShell 7+**
- **macOS / Linux / Git Bash / WSL**
  - Use `bash scripts/connect-openclaw.sh`
  - Use `bash scripts/verify-links.sh`

### 2) Handle WSL carefully

If the user is on Windows but working through **WSL**, treat the environment as Unix-like.

Before proceeding, explicitly confirm whether OpenClaw is using:
- Windows home paths such as `%USERPROFILE%\.openclaw`, or
- WSL/Linux paths such as `~/.openclaw`

Do not mix Windows paths and WSL paths in the same run.

### 3) Resolve paths

Use this precedence:

- **Toolkit root**: explicit user-provided path → `AGENT_TOOLKIT_ROOT` → default `~/.agent-toolkit`
- **OpenClaw home**: explicit user-provided path → `OPENCLAW_HOME` → default `~/.openclaw`
- **OpenClaw scripts dir**: explicit user-provided path → `OPENCLAW_SCRIPTS_DIR` → default `<openclaw-home>/scripts`

Then compute:

- **Skills source:** `<toolkit-root>/skills`
- **Skills target:** `<openclaw-home>/skills`
- **Scripts source:** `<toolkit-root>/scripts`
- **Scripts target:** `<openclaw-scripts-dir>`

### 4) Show the resolved plan before any write action

Before running any connect command, display all of the following in chat:

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

These confirmation steps are required.

### 5) Validate toolkit-local instructions

If `<toolkit-root>/docs/setup.md` exists, read it before execution and treat it as the live behavior source of truth.

Pay attention to:
- precedence rules for CLI flags, environment variables, and defaults
- supported overrides for connect and verify
- fail-safe behavior when a destination already exists as a real file or directory
- `--yes` / `-Yes` semantics
- best-effort behavior across the two OpenClaw links
- conflict behavior when the skills link path and scripts link path are identical

### 6) Require explicit approval

Do not run the connect script until the user explicitly approves the resolved paths.

Examples of sufficient approval:
- `Yes, link these paths.`
- `Proceed with these skills and scripts targets.`

If approval is missing, stop after presenting the resolved plan.

### 7) Run the connect script from the toolkit repository

After approval only, run the appropriate script from the toolkit repository.

Use explicit overrides whenever the resolved values are non-default or came from user or environment input.

#### Unix-like

```bash
bash scripts/connect-openclaw.sh \
  --toolkit-root "/resolved/toolkit-root" \
  --openclaw-home "/resolved/openclaw-home" \
  --openclaw-scripts-dir "/resolved/openclaw-scripts-dir"
```

#### Windows PowerShell 7+

```powershell
& .\scripts\connect-openclaw.ps1 `
  -ToolkitRoot "C:\resolved\toolkit-root" `
  -OpenclawHome "C:\resolved\openclaw-home" `
  -OpenclawScriptsDir "C:\resolved\openclaw-scripts-dir"
```

Use `--yes` / `-Yes` only after the user has already approved the resolved paths. It suppresses script prompts; it does not replace this skill's approval requirement.

### 8) Verify with matching overrides

Immediately run the matching verify script with the **same** override values used during connect.

#### Unix-like

```bash
bash scripts/verify-links.sh \
  --toolkit-root "/resolved/toolkit-root" \
  --openclaw-home "/resolved/openclaw-home" \
  --openclaw-scripts-dir "/resolved/openclaw-scripts-dir"
```

#### Windows PowerShell 7+

```powershell
& .\scripts\verify-links.ps1 `
  -ToolkitRoot "C:\resolved\toolkit-root" `
  -OpenclawHome "C:\resolved\openclaw-home" `
  -OpenclawScriptsDir "C:\resolved\openclaw-scripts-dir"
```

If the override values differ between connect and verify, verification can report false failures.

### 9) Report outcome clearly

Report:
- which script variant was used
- the exact skills and scripts source paths
- the exact skills and scripts target paths
- whether the connect step succeeded
- whether verification reported `OK`, `MISSING`, or `BROKEN` for:
  - `toolkit-root`
  - `openclaw/skills`
  - `openclaw/scripts`
- any remediation needed if a destination already exists as a real file or directory
- whether verification was run with matching overrides

## Output expectations

When the skill stops before execution, the user-facing output should include:
- the resolved toolkit root, OpenClaw home, and OpenClaw scripts dir
- the exact skills and scripts source and target paths
- how each resolved value was chosen
- the script variant that would be used
- a direct request for approval

After execution, the user-facing output should include:
- whether the connect step succeeded
- the verification status for `toolkit-root`, `openclaw/skills`, and `openclaw/scripts`
- any mismatch, conflict, or fail-safe refusal that blocked completion
- the next remediation step when something must be fixed manually

## Gotchas

- PowerShell 5.1 is not acceptable for the Windows PowerShell path; require `pwsh`
- In WSL, use Unix shell scripts and Linux paths only
- Do not assume default locations; resolve all paths explicitly
- The user must approve the meaningful source and target paths, not just the raw command
- `verify-links` must use the same overrides as the connect step
- If the skills target path and scripts target path are identical, stop and report the conflict
- If a target already exists as a real directory or file, stop and explain the conflict instead of overwriting it blindly
- The connect script links two OpenClaw destinations in one run; evaluate and report both, not just `skills`

## Resources

Read only when needed:
- `references/command-matrix.md` — use when choosing the correct script, matching flag names, or checking the approval checklist
- `references/eval-prompts.json` — use when testing whether the skill description triggers on the right OpenClaw toolkit-linking requests without false positives

## Portability notes

- Resolve all paths dynamically
- Use relative paths from the toolkit root when referencing toolkit-bundled scripts
- Prefer the toolkit repo's own `docs/setup.md` when present
- Do not hardcode machine-specific absolute paths
- Do not rely on interactive prompts as the primary control flow
