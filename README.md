# Agent toolkit

Single source of truth for shared agent skills, Cursor rules, setup scripts, and documentation.

## Directory layout

```
agent-toolkit/
├── README.md
├── LICENSE
├── skills/
│   ├── classify-research-papers/
│   ├── pageindex-find-papers/
│   ├── pageindex-read-papers/
│   ├── pageindex-summarize-papers/
│   ├── skill-creator/
│   └── summarize-research-papers/
├── cursor/
│   └── rules/          ← symlinked from <project>/.cursor/rules
├── scripts/            ← setup scripts (connect-openclaw, connect-cursor, verify-links)
└── docs/               ← setup and scope documentation
```

## Attachment model

Point `~/.agent-toolkit` at your local clone of this repository (for example with a symlink). The `connect-openclaw.sh` and `connect-cursor.sh` scripts (under `scripts/` when added) wire up OpenClaw and Cursor to use this tree.

For full setup instructions, see `docs/setup.md` (coming in a later ticket).
