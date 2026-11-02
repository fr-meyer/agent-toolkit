## Task

`pr-075-openclaw-long-horizon-supervisor`

Feature PRs target `dev`. Release/promotion PRs target `main`.

## Summary

- add a portable OpenClaw long-horizon supervisor skill
- use Workboard cards, claims, dependencies, proofs, and run history as the durable execution ledger
- use Automations only for exact time/event wakes and low-frequency recovery
- distinguish persistent session context from exact external conversation destinations
- require native preview/confirm or compare-and-swap receipts for non-idempotent effects and block ambiguous replay
- retain a bounded optional controller extension for fail-closed intent tracking and fenced metadata, without claiming exactly-once external effects
- merge current `dev` into the existing PR branch without rewriting its history
- bind PR #75 to the current repository-owned Speculoos exact-head contract

## Changed Files For Publish

- `.speculoos/manifest.yaml`
- `.speculoos/tasks/pr-075-openclaw-long-horizon-supervisor.yaml`
- `skills/openclaw-long-horizon-supervisor/SKILL.md`
- `skills/openclaw-long-horizon-supervisor/references/controller-contract.md`
- `skills/openclaw-long-horizon-supervisor/references/eval-prompts.json`
- `specs/pr-075-openclaw-long-horizon-supervisor/commit-message.txt`
- `specs/pr-075-openclaw-long-horizon-supervisor/pr-body.md`

## Safety Boundary

- card metadata, sessions, and Automation payloads never grant effect authority
- external, irreversible, destructive, or privacy-sensitive effects still require their native gate and authorized conversation
- ambiguous non-idempotent intents are blocked rather than replayed
- no host-specific controller, path, repository, job, session, model, or credential is hardcoded
- no Workboard, Automation, session, Gateway, or provider configuration is changed by publishing the skill
- no force-push or branch-history rewrite is used
- no check is copied, renamed, synthesized, or manually published
- no Astra fallback, auto-merge, release, deployment, settings, billing, or credential change is authorized by this packet
- Mergeguez may merge only after fresh Pullfrog review and all exact-head hosted gates succeed

## Validation

- frontmatter, reference, and portable-size checks
- valid JSON evaluation prompts and trigger/near-miss coverage
- obsolete scheduler/controller-first terminology scan
- Pullfrog workflow validator
- repository-bound Speculoos exact-head contract
- `git diff --check`
- private-data scan of added lines

## Documentation Impact

No top-level `README.md` or `docs/` file changes are needed. The complete reusable workflow and optional controller extension are documented within the new skill directory.
