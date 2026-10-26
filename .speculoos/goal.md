# Agent-toolkit exact-head Pullfrog review gate

Use Pullfrog as the primary required reviewer for shared agent-toolkit pull requests. Normal closeout requires successful `pullfrog` and `pullfrog-approval` checks attached to the current exact head, live GitHub checks, Speculoos policy validation, and explicit human merge authority.

Pullfrog remains non-pushing, non-approving, non-remediating, non-merging, and secret-free in repository source. Mergeguez review is historical only. The Mergeguez installation broker may still transport approved branches and perform explicitly authorized policy-gated merges until that separate publication role is replaced.

The repo-local metadata records public workflow policy only. Credentials, billing state, host paths, prompts, raw model output, and private runtime details remain outside the repository.
