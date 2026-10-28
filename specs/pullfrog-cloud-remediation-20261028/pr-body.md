## Summary

- add the guarded unattended Pullfrog review → remediation → exact-head re-review workflow
- invoke Pullfrog `v0.1.102` through its native `fix_review` contract while keeping provider push disabled
- persist single-record identity-bound claim, candidate, and terminal artifacts, with the sealed dispatch kept separate, at most three cycles, and three per-head attempts
- rebuild untrusted provider patches in a fresh read-only validation job, then publish only the canonical sealed patch through a separate trusted exact-head fast-forward job
- preserve independent CI/Speculoos evidence and human-only approval and stable-branch merge authority
- add a repository-owned exact-head automatic merge gate for clean same-repository feature PRs targeting any valid base except `main` or `master`, while assigning no merge actor role to Pullfrog itself
- complete Speculoos task `pullfrog-cloud-remediation-20261028`; feature PRs target `dev`, and release/promotion PRs target `main`
- replace the unreachable private cross-repository Speculoos install with a repository-bound zero-secret contract validator that persists exact-head evidence without an additional credential

## Changed Files For Publish

- `.github/workflows/pr-automation-dogfood-pr-trigger.yml`
- `.github/workflows/pr-automation-dogfood-reusable.yml`
- `.github/workflows/pullfrog-cloud-coordinator-dry-run.yml`
- `.github/workflows/pullfrog-cloud-remediation-loop.yml`
- `.github/workflows/speculoos.yml`
- `.speculoos/actors.json`
- `.speculoos/goal.md`
- `.speculoos/manifest.yaml`
- `.speculoos/publish-policy.yaml`
- `.speculoos/review-evidence.json`
- `.speculoos/tasks/pullfrog-cloud-coordinator-20261027.yaml`
- `.speculoos/tasks/pullfrog-cloud-cycle-contract-20261027.yaml`
- `.speculoos/tasks/pullfrog-cloud-remediation-20261028.yaml`
- `.speculoos/tasks/pullfrog-destination-guard-20261027.yaml`
- `README.md`
- `docs/github-actions-template-catalog.md`
- `docs/pr-automation-dogfood.md`
- `docs/pullfrog-cloud-coordinator.md`
- `docs/pullfrog-cycle-contract.md`
- `docs/pullfrog-destination-guard.md`
- `docs/pullfrog-review-only-pilot.md`
- `docs/workflow-asset-library-layout.md`
- `scripts/github/pullfrog_cloud_coordinator.py`
- `scripts/github/pullfrog_cloud_remediation.py`
- `scripts/github/pullfrog_cycle_contract.py`
- `scripts/github/pullfrog_destination_guard.py`
- `scripts/github/pullfrog_dev_auto_merge.py`
- `scripts/github/speculoos_pr_contract.py`
- `scripts/github/tests/test_pullfrog_cloud_coordinator.py`
- `scripts/github/tests/test_pullfrog_cloud_coordinator_workflow_policy.py`
- `scripts/github/tests/test_pullfrog_cloud_remediation.py`
- `scripts/github/tests/test_pullfrog_cloud_remediation_workflow_policy.py`
- `scripts/github/tests/test_pullfrog_cycle_contract.py`
- `scripts/github/tests/test_pullfrog_destination_guard.py`
- `scripts/github/tests/test_pullfrog_dev_auto_merge.py`
- `scripts/github/tests/test_pullfrog_speculoos_workflow_policy.py`
- `scripts/github/tests/test_speculoos_pr_contract.py`
- `scripts/github/validate_pullfrog_workflow.sh`
- `specs/pullfrog-cloud-coordinator-20261027/commit-message.txt`
- `specs/pullfrog-cloud-coordinator-20261027/pr-body.md`
- `specs/pullfrog-cloud-cycle-contract-20261027/commit-message.txt`
- `specs/pullfrog-cloud-cycle-contract-20261027/pr-body.md`
- `specs/pullfrog-cloud-remediation-20261028/commit-message.txt`
- `specs/pullfrog-cloud-remediation-20261028/pr-body.md`
- `specs/pullfrog-destination-guard-20261027/commit-message.txt`
- `specs/pullfrog-destination-guard-20261027/pr-body.md`
- `templates/repo-workflow-materialization-manifest.json`
- `templates/reusable-workflows/pr-automation-dogfood-reusable.yml`
- `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml`
- `templates/starter-workflows/pullfrog-cloud-coordinator-dry-run.yml`
- `templates/starter-workflows/pullfrog-cloud-remediation-loop.yml`
- `templates/starter-workflows/speculoos.yml`
## Documentation Impact

The operator-facing workflow and safety contract were updated in `README.md`, `docs/github-actions-template-catalog.md`, `docs/pr-automation-dogfood.md`, `docs/pullfrog-cloud-coordinator.md`, `docs/pullfrog-cycle-contract.md`, `docs/pullfrog-destination-guard.md`, `docs/pullfrog-review-only-pilot.md`, and `docs/workflow-asset-library-layout.md`. These files document the hosted Speculoos check, exact-head controller, repository-owned non-stable merge actor, stable promotion boundary, and credential split.

## Validation

- focused remediation and workflow-policy tests
- checksum-verified actionlint over all Pullfrog workflow copies
- full repository unit-test discovery
- Python compile, JSON parsing, actionlint-backed workflow YAML validation, canonical/materialized byte identity, and `git diff --check`
- public-safety/private-data scan
- Speculoos `validate` and `publish-check` when the local binary is available

## Security Contract

- The hosted Speculoos check executes only repository-reviewed source, fetches no private cross-repository package, receives no additional credential, and validates exact head/base identity, publication packet inventory, workflow materialization, merge actor policy, whitespace, and red-list token patterns.

- Pullfrog receives `id-token: write` for provider routing plus a job-scoped read-only GitHub token forced through `GH_TOKEN`, preventing its normal MCP write-token minting; `authorPermission: none` withholds gh and cross-run learning writes, while `push: disabled`, restricted shell, and no publication credential remain enforced.
- A separate read-only validator starts from fresh trusted-controller and exact-source checkouts, treats all provider output as untrusted, rejects forbidden paths and gitlinks, and emits the only candidate and patch the publisher may consume.
- The publisher has no provider identity token and alone receives the separately provisioned `PULLFROG_REMEDIATION_PUBLISH_TOKEN`; unlike a built-in-token push, its normal fast-forward push emits the PR synchronize event needed for unattended Pullfrog, CI, and Speculoos revalidation.
- Artifact inventory pagination must be complete, matching expired history fails closed, and PRs older than the 90-day durable-history window are ineligible for unattended remediation.
- Pushed terminal evidence is accepted only when the exact claim, candidate, publish plan, patch digest, changed-path digest, source head, and resulting head all bind to one another.
- The trusted controller re-reads exact PR identity before provider execution, candidate validation/application, and publication; it rejects forks, protected/default/base refs, stale/reused heads, workflow/governance paths, malformed history, unchanged output, repeated findings, and no-progress cycles.
- The remediation publisher's only mutation is one normal fast-forward push to the exact same-repository PR branch after the sealed patch digest and post-patch destination guard pass.
- A separate least-privilege job may merge only a clean exact-head same-repository feature PR whose base is valid and is neither `main` nor `master`; it re-reads live identity, refreshes all app-bound trusted checks and Pullfrog review evidence, rejects unresolved human changes requests, and preserves the repository's merge-commit convention.
- The coordinator carries its exact default/protected-ref policy into the digest-bound remediation claim, and the validator and publisher reuse it, so a newly eligible non-`dev` base cannot become an impossible post-provider destination.
- The mutation boundary builds a two-parent commit from the exact reviewed base and head, then submits one normal fast-forward Git receive-pack update to the literal reviewed base ref with the reviewed base SHA as the command's old OID. The server rejects any intervening base change in that same ref-update transaction, concurrent retargeting cannot redirect the push, and neither force nor force-with-lease is used. Receive-pack ref names stay byte-preserving so unrelated legal Unicode refs cannot block the selected destination.
- Because built-in-token pushes suppress ordinary push-triggered Actions runs, path-matched bounded dispatches replay only the existing `dev` cross-repository updater and reusable-ref synchronization workflows; any post-merge dispatch failure is persisted and fails visibly.
- Force-push, force-with-lease, approval, Pullfrog-native auto-merge, merges to `main` or `master`, release, deployment, settings changes, branch deletion, elevated tokens, and credential/billing changes remain out of scope.

## Publication Boundary

This commit is a locally validated source implementation. Publishing the exact commit, activating the workflow on a serving ref, and running the first hosted remediation write pilot each require separate explicit authorization. The repository-owned exact-head gate is authorized to auto-merge eligible PRs into any valid base except `main` and `master`; merges to those stable bases remain human-authorized.
