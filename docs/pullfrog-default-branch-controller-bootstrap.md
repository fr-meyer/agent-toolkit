# Pullfrog default-branch controller bootstrap

The repository default branch carries the trusted workflow and Python controller source required for GitHub to receive Pullfrog check events and run the repository-owned exact-head gate.

This bootstrap was materialized from the reviewed `feat/pullfrog-write-capable-loop` source at `c86d5dfe1e71b84ca2057c91d5f4d595204b6e0b`. Canonical workflow sources remain under `templates/`, and the live `.github/workflows/` copies are byte-identical through `templates/repo-workflow-materialization-manifest.json`.

The repository-owned auto-merge gate may merge an eligible same-repository feature PR into any valid base except exactly `main` or `master`. It refreshes app-bound exact-head evidence before mutation and performs one normal, non-force Git receive-pack update against the literal reviewed base ref and old OID. Merges into `main` or `master` remain human-authorized.

Pullfrog-native repository-wide auto-merge remains disabled. Pullfrog provider execution receives no repository publication credential. The publisher-only `PULLFROG_REMEDIATION_PUBLISH_TOKEN`, hosted remediation write pilot, approval, release, deployment, settings changes, branch deletion, force-push, and credential provisioning remain separate gates.

The serving-ref bootstrap does not merge PR #95. PR #95 must remain open until its current exact head has fresh Pullfrog, approval, CI, Speculoos, and destination evidence and this controller is proven live from the default branch.
