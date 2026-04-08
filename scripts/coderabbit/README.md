# CodeRabbit workflow helper scripts

This folder contains helper scripts for the shared reusable GitHub workflow:
- `.github/workflows/coderabbit-pr-automation.yml`

Current status:
- fetch + normalize now implement the real deterministic intake path
- preflight now implements real repo, branch, SHA, and cleanliness checks
- orchestration now implements bounded cycle control, stop reasons, and validation gating
- validation now invokes CodeRabbit CLI when available and normalizes its agent output into `validation-result.json`
- agent pass now invokes a configurable external agent command and captures structured outputs, prompt files, raw logs, and git-diff evidence
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
- The reusable workflow exposes clean caller-facing inputs for:
  - runner selection via `runner_labels_json`
  - bounded agent execution via `agent_command_json` or `agent_command`
  - validation CLI override via `coderabbit_cli`
- A GitHub-native workflow-template draft lives at:
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.yml`
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.properties.json`
- An org-level publishing layout draft lives at:
  - `docs/org-github-repo-workflow-template-layout.md`
- Agent-pass runtime configuration is supplied to the scripts via environment variables:
  - `CODERABBIT_AGENT_COMMAND_JSON` (preferred, JSON array command template)
  - `CODERABBIT_AGENT_COMMAND` (fallback string command template)
  - `CODERABBIT_CLI` (optional CodeRabbit CLI binary/path override)
- Supported command-template placeholders: `{repo_path}`, `{shared_root}`, `{pr_number}`, `{artifact_path}`, `{prompt_path}`, `{validation_path}`, `{out_dir}`.
