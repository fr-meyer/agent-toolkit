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
- `setup_agent_runtime.sh` — install and prepare the selected coding-agent runtime before remediation
- `setup_coderabbit_cli.sh` — install and authenticate the CodeRabbit CLI before validation
- `orchestrate.sh` — run the bounded remediation loop and optional validation
- `run_agent_pass.sh` — invoke the agent runtime for one bounded remediation pass
- `run_validation.sh` — run CodeRabbit validation and summarize stop conditions

Notes:
- These files are committed in the shared repo.
- Runtime checkout folders like `_shared/` and `target/` are temporary job-time paths and are not part of the repository tree.
- The reusable workflow exposes clean caller-facing inputs for:
  - runner selection via `runner_labels_json`
  - runtime preparation via `agent_runtime`
  - bounded agent execution via `agent_command_json` or `agent_command`
  - validation CLI override via `coderabbit_cli`
  - Cursor CLI override via `cursor_cli`
- A GitHub-native workflow-template draft lives at:
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.yml`
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.properties.json`
- An org-level publishing layout draft lives at:
  - `docs/org-github-repo-workflow-template-layout.md`
- Agent-pass runtime configuration is supplied to the scripts via environment variables:
  - `AGENT_RUNTIME` (`none`, `cursor`, `custom`, with room for future runtimes)
  - `CODERABBIT_AGENT_COMMAND_JSON` (preferred, JSON array command template)
  - `CODERABBIT_AGENT_COMMAND` (fallback string command template)
  - `CODERABBIT_CLI` (optional CodeRabbit CLI binary/path override)
  - `CURSOR_CLI` (optional Cursor CLI binary/path override)
- Supported command-template placeholders: `{repo_path}`, `{shared_root}`, `{pr_number}`, `{artifact_path}`, `{prompt_path}`, `{validation_path}`, `{out_dir}`.

## Consumer configuration contract

Recommended repository or organization variables:
- `CODERABBIT_RUNNER_LABELS_JSON`
- `CODERABBIT_AGENT_RUNTIME`
- `CODERABBIT_AGENT_COMMAND_JSON` or `CODERABBIT_AGENT_COMMAND`
- `CODERABBIT_CLI` (optional)
- `CURSOR_CLI` (optional)

Required secrets by feature:
- `CURSOR_API_KEY` when `agent_runtime=cursor`
- `CODERABBIT_API_KEY` when `run_validation=true`

Recommended first end-to-end configuration:
- `agent_runtime: cursor`
- `run_validation: true`
- `max_cycles: 1`
- `working_tree_must_be_clean: true`

Implementation note:
- `setup_agent_runtime.sh` installs Cursor CLI via `curl https://cursor.com/install -fsS | bash` when `agent_runtime=cursor` and the binary is not already available.
- The Cursor setup step currently verifies installation and requires `CURSOR_API_KEY` to be present for downstream headless agent commands.
- `setup_coderabbit_cli.sh` installs CodeRabbit CLI via `curl -fsSL https://cli.coderabbit.ai/install.sh | sh` and authenticates it with `coderabbit auth login --api-key "$CODERABBIT_API_KEY"`.
