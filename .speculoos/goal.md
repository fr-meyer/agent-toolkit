# Agent-toolkit exact-head Pullfrog review gate

Use Pullfrog as the primary required reviewer for shared agent-toolkit pull requests. Normal closeout requires successful `pullfrog` and `pullfrog-approval` checks attached to the current exact head, live GitHub checks, Speculoos policy validation, and explicit human merge authority.

Pullfrog may remediate its own selected review findings only after a collaborator explicitly starts **Fix all** or **Fix 👍s**. The workflow limits pushes to non-default branches, and a service-side pre-push allowlist limits them further to `feat/*`, `fix/*`, `docs/*`, `test/*`, or `chore/*`. Automatic review remediation, review approval, CI autofix, merge, release, and deployment authority remain disabled. Every remediation push invalidates earlier evidence and must be re-reviewed on its new exact head before a separate human merge decision.

Review runs use `openai/gpt-sol` at `xhigh`; review-remediation runs use `openai/gpt-luna` at `xhigh`. In pinned Pullfrog `v0.1.102`, those supported selectors resolve to `openai/gpt-6.1-sol` and `openai/gpt-6-luna`, respectively. Mergeguez review is historical only. The Mergeguez installation broker may still transport approved branches and perform explicitly authorized policy-gated merges until that separate publication role is replaced.

The repo-local metadata records public workflow policy only. Credentials, billing state, host paths, prompts, raw model output, and private runtime details remain outside the repository.
