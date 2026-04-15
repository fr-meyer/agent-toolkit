# Cross-repo workflow divergence review prompt

Use this prompt when deterministic sync is blocked because a consumer workflow appears diverged from its registered shared starter template.

## Inputs

Provide the AI reviewer with:
- shared repository slug
- consumer repository slug
- starter template path
- consumer workflow target path
- current shared starter template content
- current consumer workflow content
- bounded diff between the two
- any known historical-match result
- any pinned reusable-workflow SHA differences
- any contract differences involving inputs, secrets, permissions, or passthrough fields
- updater confidence and explicit doubts

## Task

Inspect whether the consumer workflow looks like:
1. a safe older managed version of the shared starter template,
2. an intentional consumer-specific customization,
3. or an ambiguous case that needs human adjudication.

Do not assume that a different file is necessarily wrong.
Do not assume that a historical shared model is still preferred.
Treat comments, formatting, and behavioral changes separately.

## Required output sections

### 1. Scope
- identify the shared starter template and the consumer workflow file
- state what was compared

### 2. Verified diff facts
- list only concrete, checkable differences
- separate cosmetic/comment-only changes from behavioral changes

### 3. Interpretation
- explain whether the consumer looks like an older managed copy, an intentional customization, or an ambiguous mixture
- distinguish evidence from inference

### 4. Confidence and doubts
- give a confidence level
- explicitly name any uncertainty or missing context

### 5. Recommendation
Choose exactly one:
- normalize to the shared starter template now
- keep as intentional customization and remove from exact-managed scope
- adjudicate manually before any normalization PR

If recommending normalization, say whether a proposed patch should be included in a manual-review PR.
If recommending adjudication, say what specific question the PR should ask.

## Style rules
- be concise and evidence-driven
- do not overclaim intention
- surface doubt plainly when confidence is not high
- make the report suitable for inclusion in a PR body or a committed review artifact
