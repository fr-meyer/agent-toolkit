## Summary

- supersede stale PR #86 on the current `dev` branch
- remove obsolete CodeRabbit workflows, templates, scripts, bindings, and CodeRabbit-only skills
- preserve active Pullfrog, Speculoos, workflow-distribution, and repository-similarity assets added after PR #86 diverged
- retain dated read-only consumer retirement evidence

## Task

`retire-legacy-coderabbit-assets-20261102`

## Changed Files For Publish

- `.github/workflows/coderabbit-pr-automation.yml`
- `.github/workflows/coderabbit-pr-comment-trigger.yml`
- `.github/workflows/sync-starter-workflow-template-refs-trigger.yml`
- `.speculoos/manifest.yaml`
- `.speculoos/tasks/retire-legacy-coderabbit-assets-20261102.yaml`
- `README.md`
- `docs/cross-repo-workflow-distribution-spec.md`
- `docs/cross-repo-workflow-updater-contract.md`
- `docs/evidence/pr-086-consumer-retirement.json`
- `docs/github-actions-template-catalog.md`
- `docs/workflow-asset-library-layout.md`
- `docs/workflow-authoring-rules.md`
- `scripts/coderabbit/README.md`
- `scripts/coderabbit/fetch_threads.sh`
- `scripts/coderabbit/normalize_threads.py`
- `scripts/coderabbit/orchestrate.sh`
- `scripts/coderabbit/orchestrate_core.py`
- `scripts/coderabbit/preflight.sh`
- `scripts/coderabbit/preflight_core.py`
- `scripts/coderabbit/prepare_agent_context.sh`
- `scripts/coderabbit/run_agent_pass.sh`
- `scripts/coderabbit/run_agent_pass_core.py`
- `scripts/coderabbit/run_commit_pass.sh`
- `scripts/coderabbit/run_commit_pass_core.py`
- `scripts/coderabbit/run_validation.sh`
- `scripts/coderabbit/run_validation_core.py`
- `scripts/coderabbit/setup_agent_runtime.sh`
- `scripts/coderabbit/setup_coderabbit_cli.sh`
- `scripts/github/pullfrog_dev_auto_merge.py`
- `skills/coderabbit-pr-autofix/SKILL.md`
- `skills/coderabbit-pr-automation/SKILL.md`
- `skills/coderabbit-pr-automation/references/actionable-issues.sample.json`
- `skills/coderabbit-pr-automation/references/eval-prompts.json`
- `skills/coderabbit-pr-automation/references/github-action-integration.md`
- `skills/coderabbit-pr-automation/references/issue-artifact-contract.md`
- `skills/coderabbit-pr-automation/references/pipeline-stages-and-stop-rules.md`
- `skills/coderabbit-pr-automation/references/validation-result.sample.json`
- `skills/coderabbit-pr-automation/scripts/summarize-validation-result.py`
- `skills/coderabbit-pr-automation/scripts/validate-issue-artifact.py`
- `specs/retire-legacy-coderabbit-assets-20261102/commit-message.txt`
- `specs/retire-legacy-coderabbit-assets-20261102/pr-body.md`
- `templates/cross-repo-workflow-distribution-manifest.json`
- `templates/repo-workflow-materialization-manifest.json`
- `templates/reusable-workflows/coderabbit-pr-automation.yml`
- `templates/starter-workflows/coderabbit-pr-automation-manual-trigger.yml`
- `templates/starter-workflows/coderabbit-pr-automation-pr-trigger.yml`
- `templates/starter-workflows/coderabbit-pr-comment-trigger.yml`
- `templates/starter-workflows/sync-starter-workflow-template-refs-trigger.yml`
- `templates/workflow-ref-sync-manifest.json`

## Documentation Impact

The retirement updates the public asset inventory and operating contract in:

- `README.md`
- `docs/cross-repo-workflow-distribution-spec.md`
- `docs/cross-repo-workflow-updater-contract.md`
- `docs/evidence/pr-086-consumer-retirement.json`
- `docs/github-actions-template-catalog.md`
- `docs/workflow-asset-library-layout.md`
- `docs/workflow-authoring-rules.md`

The retained documentation now identifies Pullfrog as the required exact-head AI review lane, Speculoos as the exact-head contract validator, and Mergeguez as the guarded publication and merge broker.

## Validation

Passed locally on the exact `dev` base: 242 GitHub automation tests, the pinned actionlint workflow check, manifest and ref-sync validation, Pullfrog workflow-policy validation, Python and shell syntax checks, the public PR safety scan, the Speculoos private-data scan, and `git diff --check`. Fresh hosted Pullfrog and Speculoos evidence remains mandatory on the final published head before merge.

## Related pull requests

- supersedes #86
- #79 is an exact changed-path subset of #86 and will close as superseded after merge
- #82 hardens the same retired assets and will close after merge
