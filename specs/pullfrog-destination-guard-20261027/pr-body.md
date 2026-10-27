## Summary

- bind every Pullfrog remediation attempt to the exact current PR head repository, branch, and SHA
- allow only same-repository `feat/*`, `fix/*`, `docs/*`, `test/*`, or `chore/*` destinations
- reject forks, protected/default/base branches, detached refs, stale heads, and retry destination changes
- block automatic edits to workflow and governance authority paths
- prove credentials, environment variables, and unrelated event fields cannot override the destination

## Safety boundary

This change is provider-free and side-effect-free. It does not enable Pullfrog push or perform a repository write. Hosted activation remains separately gated.

## Validation

- focused destination-guard tests
- full `scripts/github/tests` suite
- Python syntax and whitespace checks
- offline public-safety scan
- Speculoos validate and publish-check when the CLI is available
