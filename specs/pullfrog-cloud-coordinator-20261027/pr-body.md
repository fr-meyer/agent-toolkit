## Summary

- add a provider-free, read-only coordinator for exact-head Pullfrog review decisions
- require app-bound Pullfrog, CI, Speculoos, and destination-guard evidence
- model at most three remediation cycles with duplicate, no-progress, repeated-finding, unchanged-output, and reused-head stops
- materialize the canonical workflow and include it in provider-free PR automation dogfood
- make Pullfrog the sole required AI reviewer while preserving independent Speculoos evidence and human merge authority

## Changed Files For Publish

- coordinator evaluator, tests, and workflow policy tests under `scripts/github/`
- canonical and materialized coordinator workflows
- PR automation dogfood workflow integration
- workflow materialization manifest and catalog/layout documentation
- Pullfrog coordinator architecture and historical pilot clarification
- Speculoos goal, task, reviewer/actor policy, evidence declarations, and publication metadata

## Validation

- focused coordinator, cycle-contract, destination-guard, and workflow-policy tests
- checksum-verified actionlint workflow validation
- full repository unit-test discovery
- Python compile, JSON/YAML parsing, canonical/materialized byte identity, and `git diff --check`
- Speculoos validate and publish-check when the local binary is available

## Publication Boundary

This is a provider-free dry-run coordinator. It uses read-only GitHub permissions and performs no Pullfrog remediation invocation, repository write, approval, merge, rerun, release, deployment, credential, billing, settings change, or branch deletion. Publishing or activating a write-capable unattended loop requires separate explicit approval and hosted acceptance.
