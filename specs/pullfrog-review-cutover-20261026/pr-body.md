## Summary

Make Pullfrog the primary required exact-head reviewer for `fr-meyer/agent-toolkit` while preserving explicit human merge authority and keeping Pullfrog non-pushing and non-remediating.

Task: `pullfrog-review-cutover-20261026`

## Changed Files

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

## Policy change

- Require successful `pullfrog` and `pullfrog-approval` checks on the current exact PR head.
- Use Pullfrog review output as the primary review evidence.
- Treat Mergeguez review evidence as historical only.
- Retain Mergeguez only as the separate approved branch-publication broker and explicitly authorized feature-to-`dev` merge actor.
- Keep explicit human approval for every merge.

## Safety boundary

- Pullfrog push is disabled.
- Pullfrog shell is restricted.
- Pullfrog GitHub review approval is disabled.
- Review remediation, CI autofix, mentions, issue automation, labels, and auto-merge are disabled.
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

This PR changes repository policy, documentation, tests, and task metadata only. It stores no credential and changes no billing, Router funding, environment allowlist, branch protection, merge, release, or deployment setting. Feature PRs target `dev`; release/promotion PRs target `main`. Merge remains separately approval-gated.
