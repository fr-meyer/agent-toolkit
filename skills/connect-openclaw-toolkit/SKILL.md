---
name: connect-openclaw-toolkit
description: Use this skill when the user needs to link a shared toolkit repository into OpenClaw by creating or verifying the `<openclaw-home>/skills` symlink with the toolkit's `connect-openclaw` and `verify-links` scripts. Apply it for requests about wiring a toolkit to OpenClaw, fixing a broken `.openclaw/skills` link, running `connect-openclaw`, or confirming source and target paths before linking. Do not use it for Cursor-only linking, generic symlink troubleshooting unrelated to this toolkit workflow, or editing the toolkit's setup scripts themselves.
---

# Connect OpenClaw Toolkit

## Goal

Safely connect a toolkit repository's `skills` directory to OpenClaw by choosing the correct platform-specific script, resolving the exact source and target paths, obtaining explicit approval before changing anything, and then verifying the result with matching overrides.

## Default workflow

1. Confirm the request is specifically about linking toolkit skills into OpenClaw or verifying that link.
2. Determine the runtime environment and choose the correct script:
   - **Windows with PowerShell 7+ (`pwsh`)** → use `scripts/connect-openclaw.ps1` and `scripts/verify-links.ps1`
   - **macOS / Linux / Git Bash / WSL** → use `scripts/connect-openclaw.sh` and `scripts/verify-links.sh` with `bash`
3. Resolve `toolkit-root` and `openclaw-home` using the toolkit's documented precedence rules.
4. Read `<toolkit-root>/docs/setup.md` when it exists and treat it as the behavior source of truth.
5. Show the user the exact source and target paths that will be linked, plus how each was chosen.
6. Do not run the connect script until the user explicitly approves those resolved paths.
7. After approval, run the appropriate connect script with matching overrides.
8. Then run the matching `verify-links` script with the same override values and report the result.

## Scope boundaries

Use this skill for:
- Linking a toolkit repo's `skills` directory into OpenClaw
- Re-running `connect-openclaw` safely after path review
- Verifying or repairing a broken `.openclaw/skills` link for this toolkit workflow
- Explaining which script variant to use for Windows vs Unix-like environments

Do not use this skill for:
- `connect-cursor` / `.cursor/rules` setup
- Generic symlink debugging unrelated to this toolkit repo workflow
- Editing the toolkit repository's scripts or changing the underlying setup design
- Blindly running link scripts without first resolving and showing the paths

## Procedure

### 1) Identify platform and shell

Choose the script by **platform and shell**, not by filename alone:

- **Windows + PowerShell 7+ (`pwsh`)**
  - Use `scripts/connect-openclaw.ps1`
  - Use `scripts/verify-links.ps1`
- **Windows PowerShell 5.1**
  - **Stop. Do not proceed.**
  - Tell the user the PowerShell script requires **PowerShell 7+** and ask them to re-run from `pwsh`.
- **macOS / Linux / Git Bash / WSL**
  - Use `bash scripts/connect-openclaw.sh`
  - Use `bash scripts/verify-links.sh`

### 2) Handle WSL carefully

If the user is on Windows but working through **WSL**, treat the environment as Unix-like and use the `.sh` scripts with **WSL/Linux paths**.

Before proceeding in WSL, explicitly confirm whether OpenClaw is using:
- Windows home paths such as `%USERPROFILE%\.openclaw`, or
- WSL paths such as `~/.openclaw`

Do **not** mix Windows paths and WSL paths in the same run.

### 3) Resolve paths and show them

Resolve the effective values using this precedence:

- **Toolkit root**: explicit user-provided path → `AGENT_TOOLKIT_ROOT` → default `~/.agent-toolkit`
- **OpenClaw home**: explicit user-provided path → `OPENCLAW_HOME` → default `~/.openclaw`

Then compute and display these exact paths in chat before any write action:

- **Source:** `<toolkit-root>/skills`
- **Target:** `<openclaw-home>/skills`

Also show one line for how each root was chosen, for example:
- `Toolkit root: user-provided path` or `Toolkit root: AGENT_TOOLKIT_ROOT` or `Toolkit root: default ~/.agent-toolkit`
- `OpenClaw home: OPENCLAW_HOME` or `OpenClaw home: default ~/.openclaw`

These confirmation steps are **non-negotiable**.

### 4) Validate the toolkit instructions before execution

If `<toolkit-root>/docs/setup.md` exists, read it before executing and follow it as the current behavior source of truth.

Pay special attention to:
- precedence rules for CLI flags vs environment variables vs defaults
- supported overrides for `connect-openclaw` and `verify-links`
- fail-safe behavior when the destination is a real directory or file
- `--yes` / `-Yes` semantics

### 5) Require explicit approval

Do **not** run `connect-openclaw` yet.

Ask the user to explicitly approve the resolved source and target, for example:
- `Yes, link these paths.`
- `Proceed with this source and target.`

If approval is missing, stop after presenting the plan.

### 6) Run the connect script after approval

After approval only, run the correct platform-specific script.

Use explicit overrides whenever the resolved paths are non-default or were provided by the user/environment.

#### Unix-like examples

```bash
bash scripts/connect-openclaw.sh \
  --toolkit-root "/resolved/toolkit-root" \
  --openclaw-home "/resolved/openclaw-home"
```

#### Windows PowerShell 7+ examples

```powershell
& .\scripts\connect-openclaw.ps1 `
  -ToolkitRoot "C:\resolved\toolkit-root" `
  -OpenclawHome "C:\resolved\openclaw-home"
```

`--yes` / `-Yes` is optional and may be used **only after** the user has already approved the resolved paths. It suppresses the script's own overwrite prompts; it does **not** replace the skill's pre-run approval requirement.

### 7) Verify with matching overrides

Immediately after the connect step, run `verify-links` with the **same override values** used during connect.

#### Unix-like examples

```bash
bash scripts/verify-links.sh \
  --toolkit-root "/resolved/toolkit-root" \
  --openclaw-home "/resolved/openclaw-home"
```

#### Windows PowerShell 7+ examples

```powershell
& .\scripts\verify-links.ps1 `
  -ToolkitRoot "C:\resolved\toolkit-root" `
  -OpenclawHome "C:\resolved\openclaw-home"
```

If the override values differ between connect and verify, verification can report false failures.

### 8) Report outcome clearly

Report:
- which script variant was used
- the exact source and target paths
- whether `connect-openclaw` succeeded
- whether `verify-links` reported `OK`, `MISSING`, `BROKEN`, or another status
- any remediation needed if the destination already exists as a real directory or file

## Gotchas

- **PowerShell 5.1 is not acceptable** for the Windows PowerShell script path; require `pwsh`.
- For Windows users working in **WSL**, use the Unix shell script and WSL paths only.
- The connect scripts are **fail-safe**: they should not overwrite a real directory or file at the destination.
- The user's approval must cover the **meaningful paths** being linked, not just the raw command.
- `verify-links` must use the **same overrides** as the connect command or it may verify the wrong locations.

## Resources

Read only when needed:
- `references/command-matrix.md` — use when choosing the correct script, shell, flags, parameters, or approval wording

## Portability notes

- Resolve paths dynamically; do not hardcode machine-specific absolute paths into the skill.
- Prefer the toolkit repo's own `docs/setup.md` as the live behavior source when it is present.
- Use relative paths from the toolkit root when referencing bundled scripts inside that repo.
- Do not assume `~/.agent-toolkit` or `~/.openclaw` unless precedence resolution says those defaults are active.
