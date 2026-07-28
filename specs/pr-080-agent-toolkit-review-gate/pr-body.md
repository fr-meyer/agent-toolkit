## Summary

Establish repo-local Speculoos metadata for the agent-toolkit exact-head review lane.
Task: `pr-080-agent-toolkit-review-gate`

### Changed Files

- `.speculoos/actors.json`
- `.speculoos/goal.md`
- `.speculoos/manifest.yaml`
- `.speculoos/publish-policy.yaml`
- `.speculoos/review-evidence.json`
- `.speculoos/tasks/pr-080-agent-toolkit-review-gate.yaml`
- `specs/pr-080-agent-toolkit-review-gate/commit-message.txt`
- `specs/pr-080-agent-toolkit-review-gate/pr-body.md`

### Publication Boundary

This PR changes repository workflow metadata only. It does not add credentials, provider calls, application behavior, deployment, release, main-branch changes, or approval bypasses.

### Release Flow

Feature PRs target `dev`.
Release/promotion PRs target `main`.

### Documentation Impact

No user-facing documentation changes required. This PR adds only repository-local workflow metadata and task evidence needed for the exact-head review gate; no product documentation is changed.

## Validation

- Metadata YAML/JSON parse
- `git diff --check`
- Speculoos validation
- Speculoos publish-check
- Exact-head Mergeguez request dry-run for this PR's current base, branch, and head
