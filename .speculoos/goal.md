# Non-bypassable Pullfrog remediation destination guard

Add the provider-free guard that binds every automatic remediation attempt to the exact current PR head.

The guard must allow only same-repository `feat/*`, `fix/*`, `docs/*`, `test/*`, or `chore/*` heads; reject forks, detached refs, protected/default/base branches, stale heads, changed retry destinations, and workflow or governance authority paths; and ignore credentials, environment variables, and unrelated event fields as authority.

This task adds no provider call or write-capable workflow. Pullfrog remains the sole intended reviewer and fixer. Repository writes, hosted activation, approval, auto-merge, release, and deployment remain separately gated.
