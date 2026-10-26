## Summary

Add a canonical, materialized Pullfrog `v0.1.102` workflow for one bounded review-only pilot.
Task: `pullfrog-review-only-pilot-20261026`

Pullfrog remains optional comparison evidence. Exact-head Mergeguez review, Speculoos policy checks, live checks, and explicit human merge authority remain required.

### Changed Files For Publish

- `.github/workflows/pullfrog.yml`
- `.speculoos/actors.json`
- `.speculoos/goal.md`
- `.speculoos/manifest.yaml`
- `.speculoos/review-evidence.json`
- `.speculoos/tasks/pullfrog-review-only-pilot-20261026.yaml`
- `README.md`
- `docs/github-actions-template-catalog.md`
- `docs/pullfrog-review-only-pilot.md`
- `docs/workflow-asset-library-layout.md`
- `specs/pullfrog-review-only-pilot-20261026/commit-message.txt`
- `specs/pullfrog-review-only-pilot-20261026/pr-body.md`
- `templates/repo-workflow-materialization-manifest.json`
- `templates/starter-workflows/pullfrog.yml`

### Publication Boundary

This PR changes repository workflow source, its materialized runtime copy, documentation, and public policy metadata only. It adds no credential or provider-key mapping, performs no model or provider call, changes no billing, writes nothing directly to the default branch, grants no Pullfrog push, review approval, remediation, CI autofix, merge, release, deployment, or approval-bypass authority.

The workflow is inert until it is reviewed and merged to the repository default branch. Pullfrog service configuration, model access, the pilot invocation, PR merge, stable promotion, release, and deployment remain separate explicit gates.

### Release Flow

Feature PRs target `dev`.
Release/promotion PRs target `main`.

### Documentation Impact

Updated `README.md`, `docs/github-actions-template-catalog.md`, `docs/workflow-asset-library-layout.md`, and `docs/pullfrog-review-only-pilot.md` so the immutable pins, permissions, evidence role, and stop gates remain recoverable from repository source.

## Validation

- deterministic workflow materialization, including a zero-change second pass
- canonical/template byte equality
- YAML and JSON syntax validation
- immutable action pin and workflow-policy assertions
- `git diff --check`
- Speculoos validation and publish-check
- public PR safety scan after publication
- exact-head Mergeguez review before any merge
