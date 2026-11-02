# Provider-free PR automation dogfood harness

This harness is the first non-merge acceptance surface for the Pullfrog and Speculoos PR-automation architecture. It deliberately calls no coding provider and receives no secrets. Its job is to prove the deterministic boundaries before any automatic remediation is enabled.

## Roles represented by the fixture

- Pullfrog is represented as the sole AI reviewer and intended remediation worker.
- The provider-free coordinator is represented by exact-head, claim, evidence, and cycle decisions.
- Speculoos policy is represented by the independent fail-closed receipt conditions.
- Mergeguez may publish an approved branch or execute a separately authorized merge, but it is not represented as a reviewer.
- The merge mode remains human-only.

The fixture identities are public GitHub login labels, not credentials.

## What it proves

The evaluator blocks when:

- repository, base, branch, or SHA identity is malformed;
- GitHub owner/repository identity is malformed or claim deduplication differs only by case;
- the repository protected-head set is missing or malformed, or one of those
  protected branches is used as the head;
- the same claim key was already consumed;
- claim history is missing, malformed, duplicated, or contains a non-canonical claim key;
- author or reviewer labels are malformed, or the canonical identities overlap;
- review evidence belongs to an older head;
- a required-check result has a missing, malformed, or stale head SHA;
- either authoritative required check (`dogfood-contract` and `unit-tests`)
  is missing, duplicated, unnamed, replaced by an unknown name, or not successful;
- cycle bounds are invalid or exhausted;
- provider calls or secret exposure are declared;
- write scope is broader than the provider-free fixture permits;
- merge is not explicitly human-only or auto-merge is enabled.

A successful receipt is only `ready_for_human_merge`. It never performs or authorizes a merge.

## Files

- Evaluator: `scripts/github/pr_automation_dogfood.py`
- Tests and fixtures: `scripts/github/tests/`
- Canonical reusable workflow: `templates/reusable-workflows/pr-automation-dogfood-reusable.yml`
- Canonical PR trigger: `templates/starter-workflows/pr-automation-dogfood-pr-trigger.yml`
- Materialized live workflows: `.github/workflows/pr-automation-dogfood-reusable.yml` and `.github/workflows/pr-automation-dogfood-pr-trigger.yml`

## Local validation

```bash
python3 -m unittest discover -s scripts/github/tests -p 'test_pr_automation_dogfood.py' -v
python3 -m unittest discover -s scripts/github/tests -p 'test_pullfrog_*.py' -v

rm -rf artifacts/pr-automation-dogfood
mkdir -p artifacts/pr-automation-dogfood
for scenario in scripts/github/tests/fixtures/*.json; do
  name="$(basename "$scenario" .json)"
  python3 scripts/github/pr_automation_dogfood.py \
    --scenario "$scenario" \
    --out "artifacts/pr-automation-dogfood/${name}.receipt.json"
done
```

Generated receipts are local/CI artifacts and are not canonical source files.

## Security boundary

The workflow uses `contents: read`, disables checkout credential persistence, and has no secret or provider inputs. It does not run `git push`, create comments, request reviews, resolve threads, merge, deploy, or mutate branch protection. Later provider-backed workflows must be introduced through a separate reviewed change.

## Workflow-library treatment

Both live workflows are materialized from canonical `templates/` sources through `templates/repo-workflow-materialization-manifest.json`. The repo-local trigger calls the materialized reusable workflow through a relative path, so no reusable-workflow SHA diffusion mapping is needed for this dogfood pair.

The trigger includes all pull-request base branches, including nested names, then excludes exactly `main` and `master`. This lets every non-stable base eligible for the repository-owned auto-merge gate produce the required dogfood evidence without extending automatic merge authority to stable branches.
