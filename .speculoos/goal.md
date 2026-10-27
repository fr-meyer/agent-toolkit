# Exact-head Pullfrog remediation cycle contract

Define the provider-free, fail-closed decision contract for a fully unattended Pullfrog review → remediation → exact-head re-review loop.

The contract must bind repository, pull request, base, head, event, review, and required-check evidence to one exact head. It must make duplicate delivery idempotent, require a new review after every remediation commit, stop on drift or no progress, and authorize no more than three remediation cycles.

This task adds no provider call or write-capable workflow. Pullfrog remains the sole intended reviewer and fixer. Repository writes, hosted activation, approval, auto-merge, release, and deployment remain separately gated.
