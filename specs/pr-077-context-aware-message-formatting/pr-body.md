## Task

`pr-077-context-aware-message-formatting`

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Summary

- add a portable, self-contained context-aware message formatting skill
- select format from audience, urgency, channel constraints, and actionability
- distinguish ordinary updates, incident alerts, recurring reports, and external messages
- preserve privacy, factual caveats, explicit action language, and applicable external-send approval gates
- merge current `dev` into the existing PR branch without rewriting its history
- bind PR #77 to the current repository-owned Speculoos exact-head contract

## Changed Files For Publish

- `.speculoos/manifest.yaml`
- `.speculoos/tasks/pr-077-context-aware-message-formatting.yaml`
- `skills/context-aware-message-formatting/SKILL.md`
- `specs/pr-077-context-aware-message-formatting/commit-message.txt`
- `specs/pr-077-context-aware-message-formatting/pr-body.md`

## Safety Boundary

- no provider routing, delivery implementation, credential, or network behavior changes
- no private or internal-only information may be exposed merely to make a message more detailed
- no factual caveat may be removed for concision
- no force-push or branch-history rewrite is used
- no check is copied, renamed, synthesized, or manually published
- no Astra fallback, auto-merge, release, deployment, settings, billing, or credential change is authorized by this packet
- Mergeguez may merge only after fresh Pullfrog review and all exact-head hosted gates succeed

## Validation

- frontmatter enclosure and skill-name/directory identity
- portable skill size below 10,000 characters
- bounded secret-pattern scan
- Pullfrog workflow validator
- repository-bound Speculoos exact-head contract
- `git diff --check`
- private-data scan of added lines

## Documentation Impact

No top-level `README.md` or `docs/` file changes are needed. The complete reusable procedure is documented in `skills/context-aware-message-formatting/SKILL.md`.
