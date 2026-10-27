# Pullfrog cloud coordinator dry run

Add the thin, provider-free GitHub Actions coordinator for the target unattended loop:

`Pullfrog review → exact-head decision → Pullfrog remediation → fresh exact-head Pullfrog review`

This change implements only the non-mutating decision and evidence-collection stage. It binds repository, pull request, base, head, event, review, required checks, changed paths, destination, cycle history, and claim identity before reporting what the next action would be. It caps the modeled loop at three remediation cycles and stops on repeated findings, unchanged structured output, unchanged or reused heads, stale or failed evidence, forks, protected destinations, or forbidden governance paths.

Pullfrog is the sole required AI reviewer and intended fixer. Speculoos remains independent exact-head policy evidence. Mergeguez is not a reviewer; it retains only separately approved branch-publication and human-authorized merge execution duties.

The dry-run workflow uses read-only GitHub permissions, invokes no provider, writes no repository state, and always records `executed_action: none`. Remediation invocation, pushes, approval, auto-merge, release, deployment, branch deletion, hosted settings, and credentials remain separately approval-gated.
