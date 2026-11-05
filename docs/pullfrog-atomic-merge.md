# Atomic reviewed-dev merge library

`scripts/github/pullfrog_atomic_merge.py` is a transport library for a trusted
controller. It is not an enabled workflow or CLI. The historical
`pullfrog_dev_auto_merge.py` CLI and its base-only mutation methods now fail
closed; their read-only admission validators remain available.

The library creates a real merge object and object pack using the existing
Git producer. The commit must have ordered parents `[reviewed_base, reviewed_head]`
and be a normal fast-forward from the reviewed `dev` base. A single raw atomic
receive-pack request contains both the base update and a literal no-op update of
the owned source branch. A server must advertise `atomic`, v1 `report-status`
and `ofs-delta`. There is no force-push, merge-API or non-atomic fallback.

A caller must supply:

- A full same-repository PR identity, including exact author login, immutable
  account ID/type and trusted-policy schema/digest. Only `dev` and owned feature
  prefixes are eligible.
- A trusted read client and a fresh final-admission callback that re-collects
  complete current review, policy, CI, Speculoos, human-veto and applicable
  existing GitHub-rule evidence. Unknown required evidence blocks admission.
- An identity-bound local journal and a globally exclusive durable custody
  reservation before the single POST. A runner-local fsync is not durable cloud
  custody.

The final callback receives a defensive copy of the exact identity and returns
`pullfrog-final-merge-admission.v1` with `allowed: true`, that exact identity,
a bounded observation time and the full trusted snapshot digest. The operation
plan, including the candidate merge SHA, is provided to the custody callback
first. Controllers must use it when existing rules require candidate-merge
evidence. This library does not invent new required checks or change rules.

The fixed native policy is the existing three-author toolkit policy:
`fr-meyer` (User 26621962), `mergeguez[bot]` (Bot 285669409), and
`le-commis[bot]` (Bot 325213916). These are evidence-eligibility tuples, not new
GitHub permissions. The helper is loaded from verified sibling bytes in an
isolated module; ambient canonical modules, import paths, events and environment
variables cannot replace it. A workspace controller must inject its own
verified fixed policy loader explicitly.

After a timeout, unchanged refs remain ambiguous because the original server
request may finish later. Repeated calls reconcile the original journal without
replaying the POST. Exact desired refs confirm only a ref outcome. Missing,
mixed, malformed or contradictory status reports are not treated as definitive
rejection. Recovery does not invent PR closure, a `merged_by` identity or
downstream completion, and it never repeats release or deployment effects.

Publication of this source does not install a custodian, activate a controller,
change access or deploy production. Hosted acceptance of the real actor, PR
projection, existing effective rules and custody remains required before
enabling a caller.
