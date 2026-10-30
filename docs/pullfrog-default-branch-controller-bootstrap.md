# Pullfrog default-branch controller bootstrap

The repository default branch carries the trusted workflow and Python controller source required for GitHub to receive Pullfrog evidence events and run the repository-owned exact-head review, remediation, reconciliation, and merge gates.

This closure was materialized from the reviewed `feat/pullfrog-write-capable-loop` source at `ca41d2890df2c53433c19efa3d3f7f249640ef7e`. Canonical workflow sources remain under `templates/`, and the live `.github/workflows/` copies are byte-identical through `templates/repo-workflow-materialization-manifest.json`.

The review finalizer publishes `pullfrog-review-gate` only after reconstructing exact repository, PR, base, head, review, thread, profile, and digest evidence. GitHub does not emit `check_run` events for checks created by GitHub Actions, so a current valid gate performs one bounded `workflow_dispatch` handoff carrying only the exact PR number and expected head SHA. In-progress, invalid, stale, drifted, or digest-mismatched gates do not dispatch. Invalid fallback receipts use a distinct non-canonical digest and cannot authorize remediation.

The repository-owned auto-merge gate may merge an eligible same-repository feature PR into any valid base except exactly `main` or `master`. It independently refreshes app-bound exact-head review, CI, Speculoos, destination, human-review, and base identity evidence before one normal, non-force Git receive-pack update against the literal reviewed base ref and old OID. Merges into `main` or `master` remain human-authorized.

Pullfrog-native repository-wide auto-merge remains disabled. The fallback workflow is inert unless a separately approved manual dispatch authorizes one exact identity or `PULLFROG_REVIEW_FALLBACK_ENABLED` is later enabled after a successful hosted pilot. Pullfrog provider execution receives no repository publication or merge credential. The publisher-only `PULLFROG_REMEDIATION_PUBLISH_TOKEN`, hosted fallback and remediation pilots, required-check migration, release, deployment, settings changes, branch deletion, force-push, and credential provisioning remain separate gates.

The serving-ref closure does not merge PR #95. PR #95 must remain open until its current exact head has fresh Pullfrog, approval, CI, Speculoos, destination, reconciliation, and composite-gate evidence and the closure is proven live from the default branch.
