## Summary

Close out the repository-local Speculoos metadata for merged PR #81.
Task: `pr-080-agent-toolkit-review-gate`

### Changed Files

- `.speculoos/manifest.yaml`
- `.speculoos/review-evidence.json`
- `.speculoos/tasks/pr-080-agent-toolkit-review-gate.yaml`
- `.speculoos/tasks/pr-080-agent-toolkit-review-gate-closeout.yaml`
- `specs/pr-080-agent-toolkit-review-gate/closeout-commit-message.txt`
- `specs/pr-080-agent-toolkit-review-gate/closeout-pr-body.md`

### Publication Boundary

This PR changes repository workflow metadata only. It records the merged PR, exact reviewed head, Mergeguez evidence, and merge commit. It does not add credentials, provider calls, application behavior, deployment, release, main-branch changes, or approval bypasses.

### Closeout Record

- Original PR: #81
- Original head: `f6a34ddae9adf340cc00897c2966da66371d76a3`
- Merge commit: `7f059a5169e05bc665620df1df814504ce9a8118`
- Review: exact-head Mergeguez approval with 0 findings and 0 blockers
- Feature branch: intentionally retained
- GitHub Project: unavailable; no Project mutation performed

### Release Flow

Feature PRs target `dev`.
Release/promotion PRs target `main`.

### Documentation Impact

No user-facing documentation changes required: this PR updates only repository-local Speculoos workflow metadata and its public task packet; product behavior and user-facing docs are unchanged.

## Validation

- Metadata YAML/JSON parse
- Speculoos validation
- Speculoos publish-check
- `git diff --check`
- Public-data and credential-boundary scan
