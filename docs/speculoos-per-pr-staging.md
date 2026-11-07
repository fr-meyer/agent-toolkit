# Per-PR Speculoos evidence staging

The current `speculoos` workflow deliberately follows
`.speculoos/manifest.yaml` `current_task` and validates that task's complete
publication packet. A separate draft canary uses its own packet under
`specs/<task>/` instead of changing the repository-wide current task. The
legacy check therefore reports a packet mismatch for that canary; its failure
must not be reinterpreted as approval.

This change stages the `speculoos_per_pr_contract.py` previously merged on
`main`, with a NUL-delimited changed-path correction, on the `dev` line.
Its `per-pr` mode selects exactly one newly added task packet on
the PR, requires a same-repository head and matching changed-file inventory,
and rejects changes to governed workflow or policy paths. Its `manifest` mode
continues to require an explicit task matching the global pointer and checks
the candidate checkout's existing `speculoos.yml` source-to-live mapping.
Invalid UTF-8 input
returns a blocked report.

The staged script has no workflow on `dev` invoking it. In `per-pr` mode it
requires a separate `--trusted-repo` checkout and
`--expected-trusted-sha`, rejects a candidate checkout as the trusted source,
and checks that the trusted checkout is at that exact SHA. The future trusted
workflow must obtain the SHA independently from GitHub's default-branch
metadata; a caller-controlled SHA does not establish trust. The mode also
rejects `main` and `master` as bases.

The live `speculoos` workflow and `speculoos_pr_contract.py` remain untouched.
No required check is replaced, no token or App authority is introduced, and
this script is not a merge admission surface. A later reviewed workflow change
must independently validate signed, fresh per-PR evidence from a trusted
default-branch run and preserve the existing check until a replacement has
passed hosted validation and is enforced by repository policy.
