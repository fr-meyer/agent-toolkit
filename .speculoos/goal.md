# Guarded Pullfrog cloud remediation loop

Implement the fully unattended bounded loop:

`Pullfrog review → exact-head decision → native Pullfrog fix_review → trusted fast-forward publication → fresh exact-head Pullfrog/CI/Speculoos evidence`

The write-capable workflow must persist a durable claim before invoking Pullfrog, cap both remediation cycles and per-head attempts at three, and fail closed on duplicate or orphaned claims, malformed history, stale or reused heads, repeated findings, unchanged output, no progress, failed evidence, forks, protected destinations, or forbidden governance paths.

Pullfrog remains the sole required AI reviewer and fixer. The provider job has no repository write credential, is explicitly outside-author, and uses `push: disabled`; a separate read-only validator rebuilds its untrusted raw patch in a fresh exact-source checkout, and only then may a separate trusted publisher perform one exact-head normal fast-forward push after sealed-patch and post-patch destination checks pass. Speculoos remains independent exact-head policy evidence. Mergeguez is not a reviewer and retains only separately approved publication and human-authorized merge duties.

This branch implements and locally validates the source only. Publishing the exact commit, activating the workflow on a serving ref, and running the first hosted write pilot remain separately authorization-gated. Approval, auto-merge, merge, release, deployment, settings changes, force-push, branch deletion, credential changes, and billing changes remain prohibited.
