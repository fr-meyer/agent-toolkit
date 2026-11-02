## Summary

- add a deterministic provider-free contract for Pullfrog review, remediation, and exact-head re-review cycles
- bind repository, PR, base, head, event, review, and required-check evidence to one exact head
- enforce duplicate-event idempotency, no-progress stops, and a maximum of three remediation cycles
- emit sanitized machine-readable receipts without raw finding summaries

## Safety boundary

This change does not invoke Pullfrog or another provider and cannot write to a repository. Write-capable remediation remains disabled pending the destination guard, dry-run coordinator, hosted acceptance matrix, and separately authorized pilot.

## Validation

- `python3 -m unittest scripts/github/tests/test_pullfrog_cycle_contract.py -v`
- `python3 -m py_compile scripts/github/pullfrog_cycle_contract.py scripts/github/tests/test_pullfrog_cycle_contract.py`
- `git diff --check origin/dev...HEAD`
- Speculoos validate and publish-check
