# Setup

This guide wires `agent-toolkit` into OpenClaw and, optionally, into local Cursor projects.

## OpenClaw skill loading

OpenClaw should load this repository through configuration, not through symlinks under `~/.openclaw`.

Point `skills.load.extraDirs` at this repository's `skills/` directory. If you also use official upstream skill repos, add those `skills/` directories too.

Example:

```bash
openclaw config set skills.load.extraDirs '["/path/to/agent-toolkit/skills","/path/to/coderabbitai-skills/skills"]' --strict-json
openclaw config validate
```

Recommended local convention:

```text
~/Documents/GitHub/agent-toolkit/
~/Documents/GitHub/coderabbitai-skills/
```

Then configure:

```text
~/Documents/GitHub/agent-toolkit/skills
~/Documents/GitHub/coderabbitai-skills/skills
```

Do not create these legacy links anymore:

```text
~/.openclaw/skills  -> <agent-toolkit>/skills
~/.openclaw/scripts -> <agent-toolkit>/scripts
```

Runtime scripts that are required by a skill should live inside that skill's own `scripts/` directory. Repo-level scripts are reserved for repository, CI, distribution, and integration automation.

## Upstream skill repos

Do not duplicate official upstream skills in this repository when a maintained upstream repo exists.

Current example:

- `autofix` and `code-review` come from `coderabbitai/skills`
- `coderabbit-pr-automation` and `coderabbit-pr-autofix` remain in this repository because they are Franck-specific wrappers/orchestration skills

## Optional toolkit alias

Some helper scripts can resolve the repo through `~/.agent-toolkit`, but the alias is optional. You can also run scripts directly from the clone or pass `--toolkit-root`.

Create the alias only if you want the convenience path:

```bash
ln -s /path/to/agent-toolkit ~/.agent-toolkit
```

> **Windows (PowerShell 7+):**
>
> ```powershell
> New-Item -ItemType SymbolicLink -Path "$HOME\.agent-toolkit" -Target "C:\path	ogent-toolkit"
> ```
>
> If symlink creation is blocked, enable Developer Mode or run PowerShell as Administrator.

## Cursor rules setup

`connect-cursor` links the shared Cursor rules into a specific project.

From the project where you want shared Cursor rules:

```bash
/path/to/agent-toolkit/scripts/connect-cursor.sh --toolkit-root /path/to/agent-toolkit
```

If you created `~/.agent-toolkit`, you can use:

```bash
~/.agent-toolkit/scripts/connect-cursor.sh
```

The script creates:

```text
<project>/.cursor/rules -> <agent-toolkit>/cursor/rules
```

### Cursor path overrides

| Value | Bash flag | Env var | Default |
| --- | --- | --- | --- |
| Toolkit root | `--toolkit-root <path>` | `AGENT_TOOLKIT_ROOT` | `$HOME/.agent-toolkit` |
| Cursor rules target | `--cursor-rules-target <path>` | `CURSOR_RULES_TARGET` | `<toolkit-root>/cursor/rules` |
| Non-interactive approval | `--yes` | — | disabled |

PowerShell equivalents:

| Bash flag | PowerShell parameter |
| --- | --- |
| `--toolkit-root <path>` | `-ToolkitRoot <path>` |
| `--cursor-rules-target <path>` | `-CursorRulesTarget <path>` |
| `--yes` | `-Yes` |

PowerShell example:

```powershell
& "C:\path	ogent-toolkit\scripts\connect-cursor.ps1" -ToolkitRoot "C:\path	ogent-toolkit"
```

## Safety behavior

The setup scripts are fail-safe: they do not overwrite a real file or directory at the destination. If a destination already exists, inspect it and move/remove it manually only when safe.

`--yes` / `-Yes` suppresses confirmation prompts for replacing an existing wrong symlink. It does not override the fail-safe for real files or directories.

## Migration notes

If you previously used OpenClaw symlinks:

1. Remove or archive `~/.openclaw/skills` and `~/.openclaw/scripts` if they are symlinks into this repository.
2. Add this repository's `skills/` path to `skills.load.extraDirs`.
3. Add any official upstream skill repos, such as `coderabbitai/skills`, to `skills.load.extraDirs`.
4. Run `openclaw config validate`.
5. Restart or reload OpenClaw if your runtime requires it for skill-list refresh.

If the remote URL changed after the repo rename, update it normally:

```bash
git remote set-url origin <new-url>
git pull
```

The optional `~/.agent-toolkit` alias points to a filesystem path, not a remote URL. Check it with `ls -l ~/.agent-toolkit` if you keep using the alias.
