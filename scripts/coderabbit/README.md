# CodeRabbit workflow helper scripts

This folder contains helper scripts for the shared reusable GitHub workflow:
- `.github/workflows/coderabbit-pr-automation.yml`

Current status:
- first-pass draft skeleton only
- paths are designed to be relative to `github.workspace`
- consumer repo checkout is expected under a runtime folder such as `target/`
- shared repo checkout is expected under a runtime folder such as `_shared/`

Planned responsibilities:
- `fetch_threads.sh` — fetch raw PR and unresolved CodeRabbit review-thread data
- `normalize_threads.py` — normalize raw review data into `actionable-issues.json`
- `preflight.sh` — verify target repo identity, branch / SHA assumptions, and working-tree policy
- `orchestrate.sh` — run the bounded remediation loop and optional validation
- `run_agent_pass.sh` — invoke the agent runtime for one bounded remediation pass
- `run_validation.sh` — run CodeRabbit validation and summarize stop conditions

Notes:
- These files are committed in the shared repo.
- Runtime checkout folders like `_shared/` and `target/` are temporary job-time paths and are not part of the repository tree.
