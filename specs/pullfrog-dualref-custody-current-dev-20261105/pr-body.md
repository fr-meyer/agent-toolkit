## Summary

- add a separate atomic reviewed-`dev` merge library with real Git object packs,
  literal source-head compare-and-swap, fresh trusted admission and durable custody
- bind the existing three-author policy without replacing current coordinator,
  cycle, destination or review-contract schemas
- explicitly block the historical base-only CLI and mutation entrypoints
- bind this source preparation to Speculoos task `pullfrog-dualref-custody-current-dev-20261105`

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Validation

- 260 provider-free Pullfrog unit tests pass with external sockets and Git
  network denied; the 28 atomic and 27 retained legacy cases are included
- seven actual workspace producer-to-custody-to-engine composition cases pass
  using real bare Git and isolated canonical modules
- repository workflow validation passes offline using the separately prepared
  official actionlint 1.7.12 asset and its repository-pinned SHA-256
- Python compilation and diff whitespace checks pass
- exact-head Speculoos validation is required for the frozen local commit and
  again for any subsequently published revision

## Changed Files For Publish

- `.speculoos/manifest.yaml`
- `.speculoos/tasks/pullfrog-dualref-custody-current-dev-20261105.yaml`
- `docs/pullfrog-atomic-merge.md`
- `scripts/github/pullfrog_atomic_merge.py`
- `scripts/github/pullfrog_dev_auto_merge.py`
- `scripts/github/pullfrog_trusted_author_policy.json`
- `scripts/github/pullfrog_trusted_author_policy.py`
- `scripts/github/tests/test_pullfrog_atomic_merge.py`
- `scripts/github/tests/test_pullfrog_cloud_remediation_workflow_policy.py`
- `scripts/github/tests/test_pullfrog_dev_auto_merge.py`
- `scripts/github/tests/test_pullfrog_trusted_author_policy.py`
- `specs/pullfrog-dualref-custody-current-dev-20261105/commit-message.txt`
- `specs/pullfrog-dualref-custody-current-dev-20261105/pr-body.md`

## Documentation Impact

`docs/pullfrog-atomic-merge.md` describes the mandatory trusted interfaces,
intentional legacy stop, isolated policy loader and hosted acceptance boundary.

## Safety Boundary

Source preparation keeps the controller disabled. It does not publish, merge,
activate, deploy, install, change credentials, permissions, protections or
settings, or perform release/promotion. The historical integration-bootstrap
policy and existing YouTube G5 packet remain unchanged. Hosted custody, actual
actor and PR projection, and compliance with existing effective GitHub rules
remain separate acceptance gates. A timeout never authorizes an automatic replay.
