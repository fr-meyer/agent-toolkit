# Agent-toolkit exact-head review gate with bounded Pullfrog comparison

Keep shared agent-toolkit pull requests behind the fail-closed, exact-head Mergeguez review lane while preparing one review-only Pullfrog pilot as optional comparison evidence.

The Pullfrog workflow must remain non-pushing, non-approving, non-remediating, non-merging, secret-free in repository source, and separately gated on explicit model authorization. Pullfrog evidence never replaces Speculoos policy checks, required Mergeguez review, live exact-head checks, or explicit human merge authority.

The repo-local metadata records public workflow policy only. Credentials, billing state, host paths, prompts, raw model output, and private runtime details remain outside the repository.
