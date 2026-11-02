## Task

`pr-066-container-source-rebuild-guard`

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Summary

- preserve the original container source-rebuild safety change
- resynchronize the feature branch with current `dev` so the repository-owned exact-head validators are present
- add a general manual `workflow_dispatch` event to the canonical and materialized provider-free dogfood trigger
- keep all existing pull-request branch and path filters unchanged
- bind PR #66 to a dedicated Speculoos task and exact publication packet
- preserve the guarded cloud fixer's 90-day fail-closed evidence boundary for this older PR
- apply only Pullfrog's two existing findings through the protected manual publication lane, then require a fresh exact-head Pullfrog re-review

This bootstrap does not publish a check itself. GitHub Actions must execute the reviewed workflow on the exact selected ref and attach the resulting job check to that exact commit. The cloud remediation run correctly stopped with `history_retention_window_exceeded`; this packet does not weaken or bypass that guard.

## Changed Files For Publish

- `.github/workflows/pr-automation-dogfood-pr-trigger.yml`
- `.speculoos/manifest.yaml`
- `.speculoos/tasks/pr-066-container-source-rebuild-guard.yaml`
- `scripts/github/tests/test_pullfrog_cloud_remediation_workflow_policy.py`
- `skills/container-runtime-change-control/SKILL.md`
- `skills/container-runtime-change-control/tests/test_candidate_image_recipe.sh`
- `specs/pr-066-container-source-rebuild-guard/commit-message.txt`
- `specs/pr-066-container-source-rebuild-guard/pr-body.md`
- `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml`

## Safety Boundary

- no pull-request path filter is removed, changed, or broadened
- no check is copied, renamed, synthesized, or published through the Checks API
- no provider receives repository write authority
- no fallback, Astra run, force-push, approval, merge, release, deployment, settings change, billing change, or branch deletion is authorized by this packet
- no cloud-remediation retention or history guard is weakened or bypassed
- the protected manual remediation may proceed only from Pullfrog's exact findings and after fresh GitHub-hosted dogfood and Speculoos checks succeed on the exact current PR head

## Validation

- canonical/materialized dogfood workflow byte identity
- candidate-image recipe regression for rollback ordering, explicit-tag image-ID resolution, and no-pull recreate
- focused workflow policy tests
- Pullfrog workflow validator
- repository-bound Speculoos exact-head contract
- `git diff --check`
- private-data scan of added lines

## Documentation Impact

No top-level `README.md` or `docs/` file changes are part of this bootstrap. The durable capability and PR-specific operating boundary are recorded in the Speculoos task and publication packet.
