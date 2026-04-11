# Organization GitHub defaults and workflow templates

This repository provides shared GitHub-native assets for the organization.

## What lives here

- **Workflow templates** for the GitHub Actions template picker
- **Shared community health files** such as issue templates, pull request templates, and funding or support guidance, when applicable
- **Organization-wide defaults** that GitHub recognizes from a public `.github` repository

## Workflow templates

Available workflow templates live under:

- `workflow-templates/`

Current template set includes:

- `coderabbit-pr-automation-wrapper.yml`

That template creates a thin repository-local wrapper workflow which calls the reusable implementation maintained in the shared toolkit repository.

## How this template is intended to work

The CodeRabbit wrapper template does **not** embed the full automation logic here.

Instead, it:
- exposes a safe `workflow_dispatch` entrypoint in the consumer repository
- forwards the key user-facing knobs such as PR number, validation toggle, and max cycles
- calls the reusable workflow maintained in the shared toolkit repository

This split keeps the template layer small and stable while the implementation can evolve in one place.

## Backing implementation

Reusable workflow implementation lives in the shared toolkit repository, for example:

- `fr-meyer/agent-toolkit`

That repository owns:
- the reusable workflow under `.github/workflows/`
- CodeRabbit helper scripts under `scripts/coderabbit/`
- the workflow contract for normalization, preflight, orchestration, validation, and agent execution

## Consumer repository setup after using the template

After creating the wrapper workflow from the template, the consumer repository will usually define these repository or organization variables:

- `CODERABBIT_RUNNER_LABELS_JSON`
- `CODERABBIT_AGENT_RUNTIME`
- `CODERABBIT_AGENT_COMMAND_JSON` or `CODERABBIT_AGENT_COMMAND`
- `CODERABBIT_CLI` (optional)
- `CURSOR_CLI` (optional)

Typical token setup:
- `GITHUB_TOKEN` is forwarded by the wrapper as `GH_TOKEN`

Typical secret setup:
- `CURSOR_API_KEY` when `CODERABBIT_AGENT_RUNTIME=cursor`
- `CODERABBIT_API_KEY` when validation is enabled

Recommended first runtime contract:
- keep the template thin and set `CODERABBIT_AGENT_RUNTIME` to the runtime you want to prepare, for example `cursor`
- keep the actual remediation command explicit through `CODERABBIT_AGENT_COMMAND_JSON` or `CODERABBIT_AGENT_COMMAND`
- let the reusable workflow install Cursor CLI and CodeRabbit CLI only when those features are enabled

## Publishing notes

For workflow templates to appear in GitHub's native template picker, this repository should:
- be named `.github`
- be public at the organization level
- contain workflow templates under `workflow-templates/`

Each template should include:
- the workflow file, for example `coderabbit-pr-automation-wrapper.yml`
- the matching metadata file, for example `coderabbit-pr-automation-wrapper.properties.json`

## Maintenance policy

This repository should keep templates thin.

Template responsibilities:
- GitHub template-picker UX
- copy-ready wrapper workflows
- metadata for discoverability and categorization

Implementation responsibilities should stay in the shared toolkit repository.

## Related repositories

- Organization `.github` repository: template publishing and defaults
- Shared toolkit repository: reusable workflow implementation and helper scripts

## Support and ownership

If the template needs behavior changes, update the shared toolkit implementation first when possible.

Only change the wrapper template here when:
- the caller-facing contract changes
- GitHub template metadata needs updating
- the wrapper needs a new user-facing input
