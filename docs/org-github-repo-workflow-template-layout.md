# Org-level `.github` repository layout for workflow templates

This is the recommended publishing layout for GitHub-native workflow templates.

## Goal

Publish the CodeRabbit wrapper template in the place GitHub expects for organization templates, while keeping the reusable workflow itself in the shared toolkit repository.

## Recommended repositories

### 1. Organization-level template repository

Repository name:
- `.github`

Visibility:
- public

Purpose:
- expose workflow templates in GitHub's native **New workflow** template picker for repositories in the organization

### 2. Shared reusable-workflow repository

Repository name example:
- `agent-toolkit`

Visibility:
- public or private, depending on how the organization wants to share reusable workflows

Purpose:
- store the reusable workflow implementation and helper scripts

If the reusable workflow repository is private and must be callable from other private repositories in the org, enable Actions sharing for that repository.

## Exact layout

```text
<org>/.github
├── README.md
└── workflow-templates/
    ├── coderabbit-pr-automation-wrapper.yml
    └── coderabbit-pr-automation-wrapper.properties.json
```

Draft README content for that org-level repository lives at:
- `docs/org-github-repo-README.example.md`

```text
<org>/agent-toolkit
├── .github/
│   └── workflows/
│       └── coderabbit-pr-automation.yml
├── scripts/
│   └── coderabbit/
│       ├── fetch_threads.sh
│       ├── normalize_threads.py
│       ├── preflight.sh
│       ├── preflight_core.py
│       ├── orchestrate.sh
│       ├── orchestrate_core.py
│       ├── run_agent_pass.sh
│       ├── run_agent_pass_core.py
│       ├── run_validation.sh
│       └── run_validation_core.py
└── skills/
    └── coderabbit-pr-automation/
```

## Template file responsibilities

### `.github/workflow-templates/coderabbit-pr-automation-wrapper.yml`

This file should:
- be thin
- be safe to create from the template picker
- call the reusable workflow in `agent-toolkit`
- expose only the repo-local knobs that a consumer repo should care about
- rely on repository or organization variables for runtime-specific command wiring when possible

### `.github/workflow-templates/coderabbit-pr-automation-wrapper.properties.json`

This metadata file should:
- have the same base filename as the workflow template
- include `name` and `description`
- optionally include `iconName`, `creator`, `categories`, `filePatterns`, and `labels`

For final publication, the metadata can omit the `preview` label so the template appears normally in the workflow picker.

## Recommended rollout path

### Phase 1. Draft in the shared repo
- Draft the template and metadata pair
- Review the wrapper inputs and reusable-workflow reference
- Decide whether the org wants a preview-only rollout first or direct normal visibility

### Phase 2. Publish in the org `.github` repo
- Copy the two template files into:
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.yml`
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.properties.json`
- Commit to the public org `.github` repository

### Phase 3. Validate template visibility
- In a repository in the organization, open **Actions**
- Click **New workflow**
- Confirm the template appears with the expected name, icon, and description

### Optional preview-first variant
- If the organization wants a staged rollout, temporarily add `"labels": ["preview"]`
- Validate with preview mode first
- Remove the preview label for the final published version

## Consumer repository setup

After creating the workflow from the template, the consumer repo should usually define these variables:

- `CODERABBIT_RUNNER_LABELS_JSON`
- `CODERABBIT_AGENT_RUNTIME`
- `CODERABBIT_AGENT_COMMAND_JSON` or `CODERABBIT_AGENT_COMMAND`
- `CODERABBIT_CLI` (optional)
- `CURSOR_CLI` (optional)

Typical secret usage:
- `GITHUB_TOKEN` is forwarded as `GH_TOKEN`
- `CURSOR_API_KEY` is required when `CODERABBIT_AGENT_RUNTIME=cursor`
- `CODERABBIT_API_KEY` is required when validation is enabled

## Notes and caveats

- GitHub workflow templates are discovered from an organization's public `.github` repository.
- The template wrapper and the reusable workflow do not need to live in the same repository.
- Keeping the wrapper thin reduces duplication and makes the shared reusable workflow easier to evolve.
- If the reusable workflow repository is private, configure GitHub Actions access so other org repositories can call it.
- The `$default-branch` placeholder is available for templates when you need branch references to adapt automatically.

## Suggested ownership split

### `.github` repository owns
- workflow-template UX
- metadata for the template picker
- minimal wrapper file only

### `agent-toolkit` repository owns
- reusable workflow implementation
- helper scripts
- CodeRabbit normalization, preflight, orchestration, validation, and agent-pass logic
- maintenance of the runtime contract

## References

- GitHub Docs, creating workflow templates for your organization:
  - https://docs.github.com/en/actions/how-tos/reuse-automations/create-workflow-templates
- GitHub Docs, using workflow templates:
  - https://docs.github.com/en/actions/how-tos/write-workflows/use-workflow-templates
- GitHub Docs, sharing actions and workflows with your organization:
  - https://docs.github.com/en/actions/how-tos/sharing-automations/sharing-actions-and-workflows-with-your-organization
- `actions/starter-workflows` reference conventions:
  - https://github.com/actions/starter-workflows
