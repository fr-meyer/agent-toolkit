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
    ├── coderabbit-pr-automation-wrapper.properties.json
    ├── coderabbit-pr-comment-trigger.yml
    └── coderabbit-pr-comment-trigger.properties.json
```

Draft README content for that org-level repository lives at:
- `docs/org-github-repo-README.example.md`

```text
<org>/agent-toolkit
├── .github/
│   ├── workflow-template-sync-map.json
│   ├── workflows/
│   │   ├── coderabbit-pr-automation.yml
│   │   └── sync-starter-template-reusable-workflow-refs.yml
│   └── workflow-templates/
│       ├── coderabbit-pr-automation-wrapper.yml
│       ├── coderabbit-pr-automation-wrapper.properties.json
│       ├── coderabbit-pr-comment-trigger.yml
│       └── coderabbit-pr-comment-trigger.properties.json
├── scripts/
│   ├── coderabbit/
│   │   ├── fetch_threads.sh
│   │   ├── normalize_threads.py
│   │   ├── preflight.sh
│   │   ├── preflight_core.py
│   │   ├── orchestrate.sh
│   │   ├── orchestrate_core.py
│   │   ├── run_agent_pass.sh
│   │   ├── run_agent_pass_core.py
│   │   ├── run_validation.sh
│   │   └── run_validation_core.py
│   └── github/
│       ├── prepare_reusable_workflow_ref_sync_context.py
│       ├── run_repo_maintenance_agent.py
│       └── validate_reusable_workflow_refs.py
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
- Copy the relevant template files into `.github/workflow-templates/` in the public org `.github` repository
- For the current CodeRabbit starter set, that includes:
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.yml`
  - `.github/workflow-templates/coderabbit-pr-automation-wrapper.properties.json`
  - `.github/workflow-templates/coderabbit-pr-comment-trigger.yml`
  - `.github/workflow-templates/coderabbit-pr-comment-trigger.properties.json`
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
- `CODERABBIT_API_KEY` is required only when validation is explicitly enabled

## Pinned reusable-workflow ref policy

Starter templates in this repository are the canonical repo-local starting point for consumer repositories.

Rules:
- the shared reusable workflow implementation lives in `.github/workflows/` in `agent-toolkit`
- starter templates live in `.github/workflow-templates/`
- starter templates must pin both:
  - the reusable workflow `uses: ...@<sha>` reference
  - the paired `shared_repository_ref`
- for a given reusable workflow call, those two pinned values must stay identical
- when a reusable workflow changes on `main`, a follow-up maintenance commit updates the starter-template pins
- consumer repositories can adapt copied workflows locally, but this shared repository remains canonical for starter templates

Manifest format:
- this repository stores the mapping in `.github/workflow-template-sync-map.json`
- each entry names one reusable workflow source and the starter-template files it manages
- example shape:

```json
{
  "managedWorkflows": [
    {
      "source": ".github/workflows/coderabbit-pr-automation.yml",
      "templates": [
        { "path": ".github/workflow-templates/coderabbit-pr-automation-wrapper.yml" },
        { "path": ".github/workflow-templates/coderabbit-pr-comment-trigger.yml" }
      ]
    }
  ]
}
```

Maintenance flow:
1. a reusable workflow file changes on `main`
2. the maintenance workflow checks the manifest for starter-template targets
3. it prepares bounded context for only those targets
4. it updates only the mapped starter templates
5. it fails if edits escape the allowed template scope
6. it validates that `uses: ...@<sha>` and `shared_repository_ref` match the expected pinned SHA
7. it can commit the template-only sync result

Automation note:
- target discovery is manifest-driven
- starter-template updates are AI-assisted within the bounded target set
- final syntax and pin-integrity validation is deterministic

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
