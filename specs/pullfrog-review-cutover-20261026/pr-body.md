## Summary

Make Pullfrog the primary required exact-head reviewer for `fr-meyer/agent-toolkit` while preserving explicit human merge authority and allowing only explicitly triggered, branch-bounded remediation of selected Pullfrog findings.

Task: `pullfrog-review-cutover-20261026`

## Changed Files

- `.github/workflows/pullfrog.yml`
- `.speculoos/actors.json`
- `.speculoos/goal.md`
- `.speculoos/manifest.yaml`
- `.speculoos/publish-policy.yaml`
- `.speculoos/review-evidence.json`
- `.speculoos/tasks/pullfrog-review-cutover-20261026.yaml`
- `docs/github-actions-template-catalog.md`
- `docs/pr-automation-dogfood.md`
- `docs/pullfrog-review-only-pilot.md`
- `docs/workflow-asset-library-layout.md`
- `scripts/github/tests/test_pullfrog_review_cutover_policy.py`
- `scripts/github/tests/test_pullfrog_workflow_policy.py`
- `specs/pullfrog-review-cutover-20261026/commit-message.txt`
- `specs/pullfrog-review-cutover-20261026/pr-body.md`
- `templates/starter-workflows/pullfrog.yml`

## Policy change

- Require successful `pullfrog` and `pullfrog-approval` checks on the current exact PR head.
- Use Pullfrog review output as the primary review evidence.
- Treat Mergeguez review evidence as historical only.
- Retain Mergeguez only as the separate approved branch-publication broker and explicitly authorized feature-to-`dev` merge actor.
- Keep explicit human approval for every merge.
- Pin review runs to `openai/gpt-sol` at `xhigh` and remediation runs to `openai/gpt-luna` at `xhigh` through role-specific Pullfrog prompts. Pinned Pullfrog `v0.1.102` resolves those selectors to `openai/gpt-6.1-sol` and `openai/gpt-6-luna`.

## Safety boundary

- Pullfrog push is restricted to non-default branches and a service-side pre-push hook permits only `feat/*`, `fix/*`, `docs/*`, `test/*`, and `chore/*`.
- Pullfrog shell is restricted.
- Pullfrog GitHub review approval is disabled.
- **Fix all** and **Fix 👍s** require an explicit collaborator action; automatic Address reviews remain disabled.
- CI autofix, mentions, issue automation, labels, and auto-merge are disabled.
- Every remediation push requires fresh exact-head `pullfrog` and `pullfrog-approval` checks.
- No provider secret or environment mapping is added.
- The environment allowlist remains unset/empty.

## Documentation Impact

The reviewer policy and exact-head evidence requirements are updated in `docs/pullfrog-review-only-pilot.md`. The workflow catalog and custody language are updated in `docs/github-actions-template-catalog.md` and `docs/workflow-asset-library-layout.md`. The provider-free role description is updated in `docs/pr-automation-dogfood.md`. Historical task records are retained unchanged as provenance.

## Validation

- Pullfrog workflow policy tests
- Pullfrog reviewer-cutover policy tests
- provider-free dogfood tests
- checksum-verified actionlint workflow validation
- JSON and YAML parsing
- Speculoos validate and publish-check
- `git diff --check`
- public red-list scan

## Publication Boundary

This PR changes repository workflow policy, documentation, tests, and task metadata. It stores no credential and changes no billing, Router funding, environment allowlist, branch protection, merge, release, or deployment setting. The default-branch workflow bootstrap and live push enablement remain separately gated. Feature PRs target `dev`; release/promotion PRs target `main`. Merge remains separately approval-gated.
