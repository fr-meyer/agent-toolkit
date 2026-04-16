# CodeRabbit workflow helper scripts

This folder contains helper scripts for the shared reusable workflow source asset:
- `templates/reusable-workflows/coderabbit-pr-automation.yml`

Current status:
- fetch + normalize now implement the real deterministic intake path
- preflight now implements real repo, branch, SHA, and cleanliness checks
- orchestration now implements bounded cycle control, stop reasons, and validation gating
- validation now invokes CodeRabbit CLI when available and normalizes its agent output into `validation-result.json`
- agent pass now invokes a configurable external agent command and captures structured outputs, prompt files, raw logs, and git-diff evidence
- paths are designed to be relative to `github.workspace`
- shared agent context can now be materialized into the target checkout via `.agents/skills` and `.cursor/rules` before agent execution
- consumer repo checkout is expected under a runtime folder such as `target/`
- shared repo checkout is expected under a runtime folder such as `_shared/`

Planned responsibilities:
- `fetch_threads.sh` — fetch raw PR and unresolved CodeRabbit review-thread data
- `normalize_threads.py` — normalize raw review data into `actionable-issues.json`
- `preflight.sh` — verify target repo identity, branch / SHA assumptions, and working-tree policy
- `setup_agent_runtime.sh` — install and prepare the selected coding-agent runtime before remediation
- `setup_coderabbit_cli.sh` — install and authenticate the CodeRabbit CLI before validation
- `prepare_agent_context.sh` — install shared Agent Skills and Cursor rules into the target repo checkout for runtime discovery
- `orchestrate.sh` — run the bounded remediation loop and optional validation
- `run_agent_pass.sh` — invoke the agent runtime for one bounded remediation pass
- `run_commit_pass.sh` — invoke the agent runtime for post-remediation commit creation using installed Git skills
- `run_commit_pass_core.py` — prepare commit-pass prompts, filter runtime-installed files out of commit scope, preserve delegation to the installed Git skills, and capture commit-pass artifacts
- `run_validation.sh` — run CodeRabbit validation and summarize stop conditions

Notes:
- These files are committed in the shared repo.
- Runtime checkout folders like `_shared/` and `target/` are temporary job-time paths and are not part of the repository tree.
- The reusable workflow source asset exposes clean caller-facing inputs for:
  - runner selection via `runner_labels_json`
  - runtime preparation via `agent_runtime`
  - bounded agent execution via `agent_command_json` or `agent_command`
  - validation CLI override via `coderabbit_cli`
  - Cursor CLI override via `cursor_cli`
  - shared Agent Skills installation via `install_shared_skills`
  - shared Cursor rules installation via `install_cursor_rules`
  - agent context install mode via `shared_skills_install_mode`
  - post-remediation autocommit via `auto_commit`
  - commit strategy selection via `commit_strategy`
  - split-by-scope commit-count mode via `commit_count_mode`
  - fixed split-by-scope commit count via `fixed_commit_count`
  - ambiguous remainder handling via `stop_on_ambiguous_remainder`
- The commit-pass helpers are policy and scope guards only. They should not implement their own commit-message generation logic; commit planning and message drafting stay delegated to `git-repo-sync` and `changeset-commit-partitioner`.
- The current starter workflow source assets live at:
  - `templates/starter-workflows/coderabbit-pr-automation-pr-trigger.yml`
  - `templates/starter-workflows/coderabbit-pr-automation-manual-trigger.yml`
  - `templates/starter-workflows/coderabbit-pr-comment-trigger.yml`
- Layout guidance for this source-library model lives at:
  - `docs/workflow-asset-library-layout.md`
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
- `CODERABBIT_INSTALL_SHARED_SKILLS` (optional, default `true`)
- `CODERABBIT_INSTALL_CURSOR_RULES` (optional, default `true`)
- `CODERABBIT_SHARED_SKILLS_INSTALL_MODE` (optional, default `copy`)
- `CODERABBIT_AUTO_COMMIT` (optional, default `false`)
- `CODERABBIT_COMMIT_STRATEGY` (optional, default `single-commit`)
- `CODERABBIT_COMMIT_COUNT_MODE` (optional, default `auto`)
- `CODERABBIT_FIXED_COMMIT_COUNT` (optional, default `1`)
- `CODERABBIT_STOP_ON_AMBIGUOUS_REMAINDER` (optional, default `true`)

Required secrets by feature:
- `CURSOR_API_KEY` when `agent_runtime=cursor`
- `CODERABBIT_API_KEY` only when `run_validation=true`

Recommended agent-context defaults:
- install shared skills: `true`
- install Cursor rules: `true`
- install mode: `copy`

Recommended autocommit defaults:
- auto commit: `false`
- commit strategy: `single-commit`
- commit count mode: `auto`
- stop on ambiguous remainder: `true`

Recommended first end-to-end configuration for the free-tier path:
- `agent_runtime: cursor`
- `run_validation: false`
- `max_cycles: 1`
- `working_tree_must_be_clean: true`
- advisory mode only, with artifacts and diff capture but no commit or push

Implementation note:
- `setup_agent_runtime.sh` installs Cursor CLI via `curl https://cursor.com/install -fsS | bash` when `agent_runtime=cursor` and the binary is not already available.
- The Cursor setup step verifies the `agent` binary and requires `CURSOR_API_KEY` to be present for downstream headless agent commands.
- `setup_coderabbit_cli.sh` remains available for paid or explicitly enabled validation flows and authenticates with `coderabbit auth login --api-key "$CODERABBIT_API_KEY"`.
