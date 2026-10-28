# Pullfrog remediation destination guard

This provider-free guard is the non-bypassable write boundary for the unattended Pullfrog remediation loop.

It does not push, invoke a model, or authenticate to GitHub. The later coordinator must run it before remediation and again against the produced patch before any commit or push. A receipt is usable only when `status` is `allowed`.

## Allowed destination

The destination must remain the exact current pull-request head:

- same canonical repository as the target repository;
- same PR number;
- same base ref and base SHA;
- same head ref and head SHA;
- same head repository;
- same destination repository, ref, and SHA on every retry.

Fork heads are rejected. Detached/full refs are rejected. The head branch must use one of:

- `feat/`
- `fix/`
- `docs/`
- `test/`
- `chore/`

The base branch, default branch, and every protected ref are forbidden destinations.

## Retry invariant

`first_attempt` permanently binds the destination repository, branch, and SHA. Attempts are limited to three, and every retry must match both `first_attempt` and the current exact-head observation. Event fields, environment variables, credentials, and token-like values are not consulted.

## Forbidden paths

Automatic remediation cannot alter automation or governance authority. The guard blocks:

- `.github/actions/**`
- `.github/workflows/**`
- `.speculoos/**`
- `templates/reusable-workflows/**`
- `templates/starter-workflows/**`
- `.github/CODEOWNERS`
- `.github/dependabot.yml`
- `templates/repo-workflow-materialization-manifest.json`
- `templates/workflow-ref-sync-manifest.json`
- the repository-owned Pullfrog coordinator, cycle, destination, remediation, and auto-merge scripts under `scripts/github/`
- `scripts/github/speculoos_pr_contract.py`
- `scripts/github/validate_pullfrog_workflow.sh`
- the four `test_pullfrog_*workflow_policy.py` files executed by that validator

The coordinator must supply the current PR path set before remediation and the produced patch path set afterward. Candidate sealing and publication both re-run this policy, so provider output cannot replace the validator with an unconditional success or weaken its executable policy dependencies. Empty, malformed, duplicated, absolute, parent-traversing, or over-large path sets fail closed.

## Local validation

```bash
python3 -m unittest scripts/github/tests/test_pullfrog_destination_guard.py -v
python3 -m py_compile scripts/github/pullfrog_destination_guard.py scripts/github/tests/test_pullfrog_destination_guard.py
```

## Activation boundary

Passing this guard is necessary but not sufficient for a repository write. The exact-head cycle contract, dry-run coordinator, hosted acceptance matrix, and separately authorized remediation pilot must also pass before Pullfrog push is enabled.
