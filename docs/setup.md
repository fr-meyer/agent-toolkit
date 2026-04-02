# Setup

This guide helps you wire this repo into your machine and projects. It assumes you are new to the repository.

## Prerequisites

By default, scripts resolve toolkit content from `~/.agent-toolkit`, which should point at your clone of this repo. That path is the **default** toolkit root; you can bypass it when you pass `--toolkit-root` or set `AGENT_TOOLKIT_ROOT` (see [Runtime Path Overrides](#runtime-path-overrides)).

Create the default alias manually (substitute your actual clone path):

```bash
ln -s /path/to/your/clone ~/.agent-toolkit
```

> **Windows (PowerShell 7+):** Create the symlink with PowerShell (substitute your clone path):
>
> ```powershell
> New-Item -ItemType SymbolicLink -Path "$HOME\.agent-toolkit" -Target "C:\path\to\your\clone"
> ```
>
> Or equivalently from elevated `cmd.exe`: `mklink /D "%USERPROFILE%\.agent-toolkit" "C:\path\to\your\clone"`.
>
> **Junction is not used as a fallback** — the alias must be a symbolic link.
>
> If symlink creation is blocked, enable **Developer Mode** (Settings → Privacy & security → For developers) or run PowerShell as Administrator. The script will fail with a clear error if this step is skipped.

This symlink step is only needed when you want the default layout. The repository cannot know where it is cloned on each machine, so each developer who uses the default path creates this symlink once, locally.

## Runtime Path Overrides

### Configurable variables

| Variable           | CLI flag                      | Env var               | Default                          |
| ------------------ | ----------------------------- | --------------------- | -------------------------------- |
| Toolkit root       | `--toolkit-root <path>`       | `AGENT_TOOLKIT_ROOT`  | `$HOME/.agent-toolkit`           |
| OpenClaw home      | `--openclaw-home <path>`      | `OPENCLAW_HOME`       | `$HOME/.openclaw`                |
| Cursor rules target | `--cursor-rules-target <path>` | `CURSOR_RULES_TARGET` | `<toolkit-root>/cursor/rules` |

CLI flags take precedence over environment variables, which take precedence over built-in defaults.

> **Windows (PowerShell 7+):** The PowerShell scripts use the **same environment variables** (`AGENT_TOOLKIT_ROOT`, `OPENCLAW_HOME`, `CURSOR_RULES_TARGET`) and accept these named parameters in place of the Bash flags:
>
> | Bash flag | PowerShell parameter |
> | --- | --- |
> | `--toolkit-root <path>` | `-ToolkitRoot <path>` |
> | `--openclaw-home <path>` | `-OpenclawHome <path>` |
> | `--cursor-rules-target <path>` | `-CursorRulesTarget <path>` |
> | `--yes` | `-Yes` (switch) |
>
> Precedence semantics are identical: CLI parameter → env var → default.

### Applicability per script

| Variable / flag         | `connect-openclaw.sh` | `connect-cursor.sh` | `verify-links.sh` |
| ----------------------- | --------------------- | ------------------- | ----------------- |
| `--toolkit-root`        | ✓                     | ✓                   | ✓                 |
| `--openclaw-home`       | ✓                     | —                   | ✓                 |
| `--cursor-rules-target` | —                     | ✓                   | ✓                 |
| `--yes`                 | ✓                     | ✓                   | —                 |

> **Windows (PowerShell 7+):** The PowerShell equivalents follow the same applicability matrix, with `-ToolkitRoot`, `-OpenclawHome`, `-CursorRulesTarget`, and `-Yes` mapping one-to-one. `verify-links.ps1` additionally accepts `-ProjectDir` (and a positional project path), matching `verify-links.sh`’s `--project-dir` / positional argument.

### Non-default usage examples

```bash
# connect-openclaw.sh with custom toolkit root and OpenClaw home
~/.agent-toolkit/scripts/connect-openclaw.sh \
  --toolkit-root /opt/my-toolkit \
  --openclaw-home /opt/my-openclaw

# connect-cursor.sh with an explicit Cursor rules target
~/.agent-toolkit/scripts/connect-cursor.sh \
  --cursor-rules-target /opt/my-toolkit/cursor/rules

# verify-links.sh with matching overrides (use the same values as during connect)
~/.agent-toolkit/scripts/verify-links.sh \
  --toolkit-root /opt/my-toolkit \
  --openclaw-home /opt/my-openclaw \
  --cursor-rules-target /opt/my-toolkit/cursor/rules
```

> **Windows (PowerShell 7+):** Equivalent overrides:
>
> ```powershell
> # connect-openclaw.ps1 with custom toolkit root and OpenClaw home
> & "$HOME\.agent-toolkit\scripts\connect-openclaw.ps1" `
>   -ToolkitRoot C:\opt\my-toolkit `
>   -OpenclawHome C:\opt\my-openclaw
>
> # connect-cursor.ps1 with an explicit Cursor rules target
> & "$HOME\.agent-toolkit\scripts\connect-cursor.ps1" `
>   -CursorRulesTarget C:\opt\my-toolkit\cursor\rules
>
> # verify-links.ps1 with matching overrides
> & "$HOME\.agent-toolkit\scripts\verify-links.ps1" `
>   -ToolkitRoot C:\opt\my-toolkit `
>   -OpenclawHome C:\opt\my-openclaw `
>   -CursorRulesTarget C:\opt\my-toolkit\cursor\rules
> ```

### `--yes` (non-interactive mode)

`--yes` suppresses all interactive confirmation prompts. It applies to `connect-openclaw.sh` and `connect-cursor.sh`; `verify-links.sh` is read-only and has no prompts.

Prompts it suppresses include: overwriting a symlink that points to the wrong target, and proceeding when the current directory is not a git repository (Cursor script only).

It does **not** suppress the fail-safe error when the destination is a real directory or file—that always exits non-zero regardless of `--yes`.

> **Windows (PowerShell 7+):** The equivalent is the `-Yes` switch passed to `connect-openclaw.ps1` or `connect-cursor.ps1`; behavior is identical.

## Connect OpenClaw

From any directory, run the script via the stable toolkit alias (requires an effective toolkit root—either the default `~/.agent-toolkit` alias or an explicit `--toolkit-root` override):

```bash
~/.agent-toolkit/scripts/connect-openclaw.sh
```

The script accepts `--toolkit-root`, `--openclaw-home`, and `--yes`; see [Runtime Path Overrides](#runtime-path-overrides) for the full table and precedence.

Alternatively, `cd` to the root of your clone of this repo, then run `./scripts/connect-openclaw.sh`.

The script validates that the effective toolkit root is set up, then creates `<openclaw-home>/skills` as a symlink into the toolkit’s `skills` directory. It is idempotent: you can run it again safely.

> **Windows (PowerShell 7+):** From any directory, run:
>
> ```powershell
> & "$HOME\.agent-toolkit\scripts\connect-openclaw.ps1"
> ```
>
> The script accepts `-ToolkitRoot`, `-OpenclawHome`, and `-Yes` (same semantics as the Bash flags). It creates `<openclaw-home>\skills` as a **directory symbolic link** — there is no automatic junction fallback. If symlink creation fails, the script exits with remediation guidance (Developer Mode or elevated PowerShell). It is idempotent: safe to re-run.

## Connect Cursor (per project)

`cd` into the **project** directory where you want shared Cursor rules (the git root of that project), then run:

```bash
~/.agent-toolkit/scripts/connect-cursor.sh
```

The script accepts `--toolkit-root`, `--cursor-rules-target`, and `--yes`; see [Runtime Path Overrides](#runtime-path-overrides) for the full table. When `--cursor-rules-target` is provided explicitly, the toolkit root check is skipped—the script does not need the default alias in that case.

(Relative `scripts/connect-cursor.sh` only resolves if your current directory is the clone root; from a project directory, call the script through `~/.agent-toolkit/scripts/` as shown—or invoke it from the clone with matching `--toolkit-root` if you use overrides.)

The script detects the git project root and creates `.cursor/rules` as a symlink to the effective Cursor rules target. If you run it outside a git repository, you will get a confirmation prompt before it proceeds (unless you pass `--yes`).

> **Windows (PowerShell 7+):** `cd` into the project directory, then run:
>
> ```powershell
> & "$HOME\.agent-toolkit\scripts\connect-cursor.ps1"
> ```
>
> The script accepts `-ToolkitRoot`, `-CursorRulesTarget`, and `-Yes`. The `.cursor\rules` link is created in **`$PWD`** (strict parity with Bash — not at the detected git root, even if git is available). If the current directory is not a git repository, the script prints a warning and prompts for confirmation; `-Yes` suppresses the prompt and proceeds automatically. It creates a **directory symbolic link** only; there is no junction fallback. Developer Mode or elevated PowerShell is required if symlink creation is blocked.

## Verify links

From any directory (with the toolkit root accessible—default alias or matching overrides):

```bash
~/.agent-toolkit/scripts/verify-links.sh
```

Alternatively, `cd` to your clone root and run `./scripts/verify-links.sh`.

The script accepts `--toolkit-root`, `--openclaw-home`, and `--cursor-rules-target`; see [Runtime Path Overrides](#runtime-path-overrides).

> **Note:** Invoke `verify-links.sh` with the **same override values** you used when running the connect scripts. If overrides differ (or are omitted when non-default paths were used), verification targets the wrong paths and can report false failures.

Output includes per-link status (`OK`, `MISSING`, or `BROKEN`) and a one-line summary.

You can pass an optional project path so the script checks that project’s Cursor link explicitly. Both of these forms are accepted:

```bash
# positional form
~/.agent-toolkit/scripts/verify-links.sh /path/to/project

# flag form
~/.agent-toolkit/scripts/verify-links.sh --project-dir /path/to/project
```

> **Windows (PowerShell 7+):**
>
> ```powershell
> # positional form
> & "$HOME\.agent-toolkit\scripts\verify-links.ps1" C:\path\to\project
>
> # flag form
> & "$HOME\.agent-toolkit\scripts\verify-links.ps1" -ProjectDir C:\path\to\project
> ```

If both forms are provided with **different** values, the script exits immediately with an argument error.

Without a project argument, the script uses the current directory when it looks like a project; if it does not, it skips the Cursor-related check and says so explicitly.

Exit codes: `0` means all required checks passed; a non-zero exit code means at least one issue was found.

> **Windows (PowerShell 7+):** From any directory:
>
> ```powershell
> & "$HOME\.agent-toolkit\scripts\verify-links.ps1"
> ```
>
> The script accepts `-ToolkitRoot`, `-OpenclawHome`, `-CursorRulesTarget`, and `-ProjectDir` (or a positional project path). Output tokens (`OK`, `MISSING`, `BROKEN`, `SKIPPED`) and the one-line summary format are identical to Bash output. **Strict git parity:** if `git rev-parse --show-toplevel` cannot run and no explicit project path is provided, the Cursor check is reported as `SKIPPED` (not a failure). Canonical path comparisons use `GetFinalPathNameByHandle` raw outputs (via `Resolve-CanonicalPath` in `LinkUtils.psm1`) — not `realpath` or PowerShell’s `Resolve-Path`. Use the same override-matching rule as on Bash: invoke with the same `-ToolkitRoot`, `-OpenclawHome`, and `-CursorRulesTarget` values you used during connect, or verification will target wrong paths.

## Remediation — destination already exists as a real directory or file

The connect scripts are fail-safe: they **never** overwrite a real directory or file at the link destination.

If a script refuses to create a link because something already exists:

1. Inspect the existing path to see what it is.
2. Back it up or remove it manually only if that is safe for your setup.
3. Re-run the connect script.

This behavior is intentional: the scripts protect existing data on your machine.

> **Windows (PowerShell 7+):** The fail-safe behavior (refusing to overwrite a real directory or file at the link destination) is **identical on Windows** — the `.ps1` scripts exit non-zero with the same remediation message, and no automatic fallback is attempted.

## Migration — existing clones after the repo rename

This project uses a strict cutover: there is no compatibility layer for the old `shared-agent-skills` remote name or layout assumptions in these docs.

If you already had a clone and the remote URL changed:

1. Update the remote: `git remote set-url origin <new-url>`
2. Confirm it works: `git pull`
3. **Verify the alias** (or your chosen toolkit root): confirm `~/.agent-toolkit` (or `readlink`/path for your `--toolkit-root`) resolves to the clone you intend—for example `readlink -f ~/.agent-toolkit` or `ls -l ~/.agent-toolkit`. The printed path should be your updated local repository root.
4. **Verify links** (final health check): `~/.agent-toolkit/scripts/verify-links.sh` (using the same overrides if non-default paths are in use).

Your default `~/.agent-toolkit` symlink is unaffected by the rename: it points at a path on your filesystem, not at the git remote URL. If you ever pointed the symlink (or override) at a different directory, step 3 catches that before link checks run.
