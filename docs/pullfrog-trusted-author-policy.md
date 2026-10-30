# Pullfrog trusted-author policy

Pullfrog review eligibility and repository mutation authority are separate decisions.
A valid review may be collected for any valid pull-request author, including an
external contributor or fork. A review never grants permission to remediate,
publish, reconcile threads, approve, or merge.

## Canonical authority source

The reviewed mutation allowlist is:

- policy parser: `scripts/github/pullfrog_trusted_author_policy.py`
- policy artifact: `scripts/github/pullfrog_trusted_author_policy.json`
- focused tests: `scripts/github/tests/test_pullfrog_trusted_author_policy.py`

The parser loads only the sibling repository-owned JSON artifact. Runtime paths,
environment variables, event fields, workflow inputs, and pull-request content
cannot select another policy file. The policy is bound to
`fr-meyer/agent-toolkit` and has no login-only fallback.

## Identity rule

The positive numeric GitHub account ID is the primary authority. The current
case-folded login and exact GitHub account type must also match the reviewed
entry. A missing ID, unknown account, reused login, rename, recreated account,
or `User`/`Bot` type drift stops write authority.

The initial trusted mutation identities are:

| Account ID | Login | GitHub type |
| ---: | --- | --- |
| `26621962` | `fr-meyer` | `User` |
| `285669409` | `mergeguez[bot]` | `Bot` |
| `325213916` | `le-commis[bot]` | `Bot` |

GitHub `node_id` may be retained as diagnostic evidence, but it is never an
authorization key and does not enter the policy digest.

## Canonical digest

The parser rejects unknown fields, duplicate JSON keys, duplicate account IDs,
duplicate logins, malformed repositories, non-positive or boolean IDs,
non-canonical logins, and login/type inconsistencies. It sorts normalized entries
by numeric account ID and computes SHA-256 over canonical compact JSON. The
initial reviewed policy digest is
`657eaab8a92d2517165f59a2746770ccfac70c340235040bf45aaca7b577b41f`.
Any reviewed policy change therefore creates a new digest, requires an explicit
test-vector update, and invalidates mutation evidence bound to an older digest.

## Mutation boundary

The parser, artifact, and focused tests are protected automation-authority paths.
Automatic remediation cannot change them. Later controller integration must load
the policy from trusted default-branch controller source, bind its digest and the
live PR author ID/login/type into every exact-head evidence contract, and re-read
both immediately before each authority transition.

This policy source does not itself authorize a hosted run, publication, settings
change, credential provisioning, approval, merge, release, deployment, or branch
deletion.

## Local validation

```bash
python3 -I scripts/github/tests/test_pullfrog_trusted_author_policy.py -v
python3 -I scripts/github/tests/test_pullfrog_destination_guard.py -v
python3 -m py_compile \
  scripts/github/pullfrog_trusted_author_policy.py \
  scripts/github/tests/test_pullfrog_trusted_author_policy.py
```
