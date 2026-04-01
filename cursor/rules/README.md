# Cursor rules

**What goes here:** Cursor rule files (`.mdc`) that define shared agent behavior, coding conventions, and workflow rules for use in Cursor-based projects.

**File format:** Each rule file uses the `.mdc` format — a Markdown-based format with optional YAML frontmatter that Cursor reads to configure its AI behavior in a project.

**How it is consumed:** Projects do not copy these files. Instead, each project symlinks its `.cursor/rules` directory to this folder:

```
<project>/.cursor/rules → ~/.agent-toolkit/cursor/rules
```

The `~/.agent-toolkit` alias must point to the local clone of this repo. The `connect-cursor.sh` script (added in a later ticket) automates creating this symlink.
