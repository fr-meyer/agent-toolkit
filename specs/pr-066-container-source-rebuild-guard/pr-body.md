## Task

`pr-066-container-source-rebuild-guard`

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Summary

- preserve the original container source-rebuild safety change
- resynchronize the feature branch with current `dev` so the repository-owned exact-head validators are present
- add a general manual `workflow_dispatch` event to the canonical and materialized provider-free dogfood trigger
- keep all existing pull-request branch and path filters unchanged
- bind PR #66 to a dedicated Speculoos task and exact publication packet

This bootstrap does not publish a check itself. GitHub Actions must execute the reviewed workflow on the exact selected ref and attach the resulting job check to that exact commit.

## Changed Files For Publish

- `.github/workflows/pr-automation-dogfood-pr-trigger.yml`
- `.speculoos/manifest.yaml`
- `.speculoos/tasks/pr-066-container-source-rebuild-guard.yaml`
- `scripts/github/tests/test_pullfrog_cloud_remediation_workflow_policy.py`
- `skills/container-runtime-change-control/SKILL.md`
- `specs/pr-066-container-source-rebuild-guard/commit-message.txt`
- `specs/pr-066-container-source-rebuild-guard/pr-body.md`
- `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml`

## Safety Boundary

- no pull-request path filter is removed, changed, or broadened
- no check is copied, renamed, synthesized, or published through the Checks API
- no provider receives repository write authority
- no fallback, Astra run, force-push, approval, merge, release, deployment, settings change, billing change, or branch deletion is authorized by this packet
- the guarded Pullfrog loop may proceed only after fresh GitHub-hosted dogfood and Speculoos checks succeed on the exact current PR head

## Validation

- canonical/materialized dogfood workflow byte identity
- focused workflow policy tests
- Pullfrog workflow validator
- repository-bound Speculoos exact-head contract
- `git diff --check`
- private-data scan of added lines

## Documentation Impact

No top-level `README.md` or `docs/` file changes are part of this bootstrap. The durable capability and PR-specific operating boundary are recorded in the Speculoos task and publication packet.
