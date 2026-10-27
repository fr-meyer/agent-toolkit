# Agent-toolkit exact-head Pullfrog review gate

Use Pullfrog as the primary required reviewer for shared agent-toolkit pull requests. Normal closeout requires successful `pullfrog` and `pullfrog-approval` checks attached to the current exact head, live GitHub checks, Speculoos policy validation, and explicit human merge authority.

Pullfrog remains non-pushing, non-approving, non-remediating, non-merging, and secret-free in repository source. Pinned Pullfrog `v0.1.102` skips its service-side pre-push hook after the first hook failure, so that hook is not accepted as a branch-authorization boundary. **Fix all** and **Fix 👍s** must remain unused until a non-bypassable destination guard rejects both the first forbidden push attempt and a retry, and re-enablement receives separate explicit authorization.

Review runs use `openai/gpt-sol` at `xhigh`, which pinned Pullfrog `v0.1.102` resolves to `openai/gpt-6.1-sol`. `openai/gpt-luna` at `xhigh`, resolving to `openai/gpt-6-luna`, is retained only as the inactive target for a future separately authorized remediation path. Mergeguez review is historical only. The Mergeguez installation broker may still transport approved branches and perform explicitly authorized policy-gated merges until that separate publication role is replaced.

The repo-local metadata records public workflow policy only. Credentials, billing state, host paths, prompts, raw model output, and private runtime details remain outside the repository.
