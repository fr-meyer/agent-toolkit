# Setup

This guide helps you wire this repo into your machine and projects. It assumes you are new to the repository.

## Prerequisites

Before you run any script here, `~/.agent-toolkit` must exist and point at your clone of this repo.

Create the alias manually (substitute your actual clone path):

```bash
ln -s /path/to/your/clone ~/.agent-toolkit
```

This is the only step that is not scripted. The repository cannot know where it is cloned on each machine, so each developer creates this symlink once, locally.

## Connect OpenClaw

From any directory, run the script via the stable toolkit alias (requires `~/.agent-toolkit` from [Prerequisites](#prerequisites)):

```bash
~/.agent-toolkit/scripts/connect-openclaw.sh
```

Alternatively, `cd` to the root of your clone of this repo, then run `./scripts/connect-openclaw.sh`.

The script validates that `~/.agent-toolkit` is set up, then creates `~/.openclaw/skills` as a symlink to `~/.agent-toolkit/skills`. It is idempotent: you can run it again safely.

## Connect Cursor (per project)

`cd` into the **project** directory where you want shared Cursor rules (the git root of that project), then run:

```bash
~/.agent-toolkit/scripts/connect-cursor.sh
```

(Relative `scripts/connect-cursor.sh` only resolves if your current directory is the clone root; from a project directory, call the script through `~/.agent-toolkit/scripts/` as shown.)

The script detects the git project root and creates `.cursor/rules` as a symlink to `~/.agent-toolkit/cursor/rules`. If you run it outside a git repository, you will get a confirmation prompt before it proceeds.

## Verify links

From any directory (with `~/.agent-toolkit` set up):

```bash
~/.agent-toolkit/scripts/verify-links.sh
```

Alternatively, `cd` to your clone root and run `./scripts/verify-links.sh`.

Output includes per-link status (`OK`, `MISSING`, or `BROKEN`) and a one-line summary.

You can pass an optional project path so the script checks that project’s Cursor link explicitly:

```bash
~/.agent-toolkit/scripts/verify-links.sh /path/to/project
```

Without that argument, the script uses the current directory when it looks like a project; if it does not, it skips the Cursor-related check and says so explicitly.

Exit codes: `0` means all required checks passed; a non-zero exit code means at least one issue was found.

## Remediation — destination already exists as a real directory or file

The connect scripts are fail-safe: they **never** overwrite a real directory or file at the link destination.

If a script refuses to create a link because something already exists:

1. Inspect the existing path to see what it is.
2. Back it up or remove it manually only if that is safe for your setup.
3. Re-run the connect script.

This behavior is intentional: the scripts protect existing data on your machine.

## Migration — existing clones after the repo rename

This project uses a strict cutover: there is no compatibility layer for the old `shared-agent-skills` remote name or layout assumptions in these docs.

If you already had a clone and the remote URL changed:

1. Update the remote: `git remote set-url origin <new-url>`
2. Confirm it works: `git pull`
3. **Verify the alias**: confirm `~/.agent-toolkit` resolves to the clone you intend (for example `readlink -f ~/.agent-toolkit` or `ls -l ~/.agent-toolkit`). The printed path should be your updated local repository root.
4. **Verify links** (final health check): `~/.agent-toolkit/scripts/verify-links.sh`

Your `~/.agent-toolkit` symlink is unaffected by the rename: it points at a path on your filesystem, not at the git remote URL. If you ever pointed the symlink at a different directory, step 3 catches that before link checks run.
