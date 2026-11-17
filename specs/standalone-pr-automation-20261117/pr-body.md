## Summary

- Add explicit-request standalone Pullfrog control contracts without mandatory Speculoos, CodeRabbit or auto-merge.
- Compose real admission, recommendation-only Decision, credential-separated execution plans, exact-head review collection and publication reconciliation.
- Enforce immutable original deadlines, Decision elapsed time, conserved usage and pre-provider destination binding; fix both independent review findings.
- Add atomic local CAS/restart journal, an explicitly disabled read-only admission diagnostic and credential-free contract CI.
- Add a pure typed Decision codec pinned to trusted OpenClaw source, transactional-state conformance and a fail-closed execution-profile verification seam.
- Repair observed Pullfrog findings for ordinary descendant cleanup, late publication reconciliation and a second proven-free attempt.

## Scope and limitations

Source-only foundation: not a qualified hosted coding loop. No provider/CLI call,
credential/configuration write, publisher activation, merge, deployment or cost
change is part of this PR. Local journal/artifact tests do not prove hosted durable
claims. Exact Decision transport, coding CLI/model custody and isolation, hard
billing stop, genuine live Pullfrog identity and separate publisher qualification
remain live acceptance gates. See docs/standalone-pr-automation.md.

Feature PRs target `dev`; release/promotion PRs target `main`.

## Validation

- 436 full Pullfrog regression tests and 10 contribution-contract tests passed on the integrated source successor. Exact committed-candidate validation is recorded before publication.
- Canonical/materialized workflow equality, checksum-pinned actionlint and protected workflow-policy validator passed.
- Python compilation and whitespace/privacy checks are required on the exact source candidate before publication.
- Original and subsequent independent/Pullfrog findings are reproduced and repaired; focused successor verification is recorded before publication. No fixture result qualifies hosted isolation, billing or provider custody.

## Documentation Impact

README.md, docs/github-actions-template-catalog.md and docs/standalone-pr-automation.md document the new source surfaces, disabled diagnostic, credential-free CI and unresolved live qualification gates.

## Publication Boundary

Source-only branch/PR approval does not authorize any credential change, provider call, deployment, release, serving activation or merge. Those remain separate exact-scope approval and qualification gates. No auto-merge.

## Approval And Rollback

Owner approved the standalone plan and parallel implementation on 2026-11-17.
Only this source PR is proposed. No auto-merge or serving activation. Rollback is
to close the source PR or revert a separately approved merge; preserve journals,
recovery branches and evidence. Existing unrelated task holds are unchanged.

## Changed Files For Publish

- .github/workflows/pullfrog-standalone-admission.yml
- .github/workflows/pullfrog-standalone-ci.yml
- .speculoos/manifest.yaml
- .speculoos/tasks/standalone-pr-automation-20261117.yaml
- README.md
- docs/github-actions-template-catalog.md
- docs/standalone-pr-automation.md
- scripts/github/pullfrog_cloud_remediation.py
- scripts/github/pullfrog_destination_guard.py
- scripts/github/pullfrog_standalone_admission.py
- scripts/github/pullfrog_standalone_collector.py
- scripts/github/pullfrog_standalone_contract.py
- scripts/github/pullfrog_standalone_controller.py
- scripts/github/pullfrog_standalone_decision.py
- scripts/github/pullfrog_standalone_decision_codec.py
- scripts/github/pullfrog_standalone_execution.py
- scripts/github/pullfrog_standalone_execution_profile.py
- scripts/github/pullfrog_standalone_github.py
- scripts/github/pullfrog_standalone_policy.json
- scripts/github/pullfrog_standalone_review.py
- scripts/github/pullfrog_standalone_store.py
- scripts/github/pullfrog_standalone_worker.py
- scripts/github/speculoos_pr_contract.py
- scripts/github/tests/test_pullfrog_standalone_a.py
- scripts/github/tests/test_pullfrog_standalone_c.py
- scripts/github/tests/test_pullfrog_standalone_collector.py
- scripts/github/tests/test_pullfrog_standalone_controller.py
- scripts/github/tests/test_pullfrog_standalone_decision.py
- scripts/github/tests/test_pullfrog_standalone_decision_codec.py
- scripts/github/tests/test_pullfrog_standalone_execution_c.py
- scripts/github/tests/test_pullfrog_standalone_execution_profile.py
- scripts/github/tests/test_pullfrog_standalone_github.py
- scripts/github/tests/test_pullfrog_standalone_pullfrog_fixes.py
- scripts/github/tests/test_pullfrog_standalone_review.py
- scripts/github/tests/test_pullfrog_standalone_store.py
- scripts/github/tests/test_speculoos_pr_contract.py
- scripts/github/validate_pullfrog_workflow.sh
- specs/standalone-pr-automation-20261117/commit-message.txt
- specs/standalone-pr-automation-20261117/pr-body.md
- templates/repo-workflow-materialization-manifest.json
- templates/starter-workflows/pullfrog-standalone-admission.yml
- templates/starter-workflows/pullfrog-standalone-ci.yml
