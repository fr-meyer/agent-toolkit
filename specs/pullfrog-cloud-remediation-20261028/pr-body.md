## Summary

- add the guarded unattended Pullfrog review → remediation → exact-head re-review workflow
- invoke Pullfrog `v0.1.102` through its native `fix_review` contract while keeping provider push disabled
- persist single-record identity-bound claim, candidate, and terminal artifacts, with the sealed dispatch kept separate, at most three cycles, and three per-head attempts
- rebuild untrusted provider patches in a fresh read-only validation job, then publish only the canonical sealed patch through a separate trusted exact-head fast-forward job
- preserve independent CI/Speculoos evidence and human-only approval and merge authority

## Changed Files For Publish

- remediation controller and focused tests under `scripts/github/`
- canonical and materialized remediation workflow
- checksum-verified actionlint validation coverage
- workflow materialization manifest, catalog, layout, and coordinator documentation
- Speculoos goal, task, actor/reviewer policy, evidence declarations, and publication metadata

## Validation

- focused remediation and workflow-policy tests
- checksum-verified actionlint over all Pullfrog workflow copies
- full repository unit-test discovery
- Python compile, JSON/YAML parsing, canonical/materialized byte identity, and `git diff --check`
- public-safety/private-data scan
- Speculoos `validate` and `publish-check` when the local binary is available

## Security Contract

- Pullfrog receives `id-token: write` for provider routing plus a job-scoped read-only GitHub token forced through `GH_TOKEN`, preventing its normal MCP write-token minting; `authorPermission: none` withholds gh and cross-run learning writes, while `push: disabled`, restricted shell, and no publication credential remain enforced.
- A separate read-only validator starts from fresh trusted-controller and exact-source checkouts, treats all provider output as untrusted, rejects forbidden paths and gitlinks, and emits the only candidate and patch the publisher may consume.
- The publisher has no provider identity token and alone receives the separately provisioned `PULLFROG_REMEDIATION_PUBLISH_TOKEN`; unlike a built-in-token push, its normal fast-forward push emits the PR synchronize event needed for unattended Pullfrog, CI, and Speculoos revalidation.
- Artifact inventory pagination must be complete, matching expired history fails closed, and PRs older than the 90-day durable-history window are ineligible for unattended remediation.
- Pushed terminal evidence is accepted only when the exact claim, candidate, publish plan, patch digest, changed-path digest, source head, and resulting head all bind to one another.
- The trusted controller re-reads exact PR identity before provider execution, candidate validation/application, and publication; it rejects forks, protected/default/base refs, stale/reused heads, workflow/governance paths, malformed history, unchanged output, repeated findings, and no-progress cycles.
- The only repository mutation is one normal fast-forward push to the exact same-repository PR branch after the sealed patch digest and post-patch destination guard pass.
- Force-push, force-with-lease, approval, auto-merge, merge, release, deployment, settings changes, branch deletion, elevated tokens, and credential/billing changes remain out of scope.

## Publication Boundary

This commit is a locally validated source implementation. Publishing the exact commit, activating the workflow on a serving ref, and running the first hosted write pilot each require separate explicit authorization. Every merge remains human-authorized.
