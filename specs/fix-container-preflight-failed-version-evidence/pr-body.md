## Task

`fix-container-preflight-failed-version-evidence`

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Summary

- reject live-version stdout when the probe exits unsuccessfully
- keep the live version unknown after failed probes so mutating operations cannot be declared safe
- sanitize failure reporting to the exit status rather than publishing raw probe diagnostics
- preserve successful-probe behavior
- merge current `dev` into the existing PR branch without rewriting its history
- bind PR #88 to the current repository-owned Speculoos exact-head contract

## Changed Files For Publish

- `.speculoos/manifest.yaml`
- `.speculoos/tasks/fix-container-preflight-failed-version-evidence.yaml`
- `skills/container-runtime-change-control/scripts/container-runtime-preflight.sh`
- `skills/container-runtime-change-control/tests/test_container_runtime_preflight.sh`
- `specs/fix-container-preflight-failed-version-evidence/commit-message.txt`
- `specs/fix-container-preflight-failed-version-evidence/pr-body.md`

## Safety Boundary

- no failed probe output is accepted as version evidence
- no raw failed-probe stderr is published
- no force-push or branch-history rewrite is used
- no check is copied, renamed, synthesized, or manually published
- no provider receives repository write authority
- no Astra fallback, auto-merge, release, deployment, settings, billing, or credential change is authorized by this packet
- Mergeguez may merge only after fresh Pullfrog review and all exact-head hosted gates succeed

## Validation

- shell syntax checks for the preflight helper and regression suite
- full container-runtime preflight regression suite
- Pullfrog workflow validator
- repository-bound Speculoos exact-head contract
- `git diff --check`
- private-data scan of added lines

## Documentation Impact

No top-level `README.md` or `docs/` file changes are needed. The behavior is covered by the helper regression suite and this PR-specific Speculoos task and publication packet.
