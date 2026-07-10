---
name: external-skill-repo-scope-router
description: Use this skill when a user wants to install, add, clone, import, evaluate, or make visible an external Git/GitHub skill repository, skill pack, or AgentSkills-compatible repo, and the target runtime or visibility scope may be ambiguous. Decide whether the request should use a shared/package-managed install, workspace-local skill, runtime-private install, marketplace/registry install, or only an audit/reference pass. Do not use it for creating brand-new skill content or for executing a platform-specific install after the target adapter is already clear.
---

# External Skill Repo Scope Router

## Goal

Decide the correct install scope before touching files or using a runtime-specific installer for an external skill repository.

This skill is generic across agent platforms. It does not clone, install, edit config, approve code, or choose platform-specific commands. It produces a routing decision and then delegates execution to the right platform adapter, such as an OpenClaw extraDir installer, a Codex-only installer, or a marketplace workflow.

## Scope receipt

- Portability tier: `generic-shared`.
- Reusable invariant: external skill repos need a visibility decision before install mechanics.
- Local adapters: platform-specific installers own exact paths, config keys, reload commands, registry APIs, and validation commands.
- Excluded facts: personal names, host paths, private repo names, account ids, credentials, and incident history.

## Use this skill for

- deciding where an external skill repo should be installed;
- preventing a shared/runtime-wide request from being satisfied by a private agent folder;
- comparing package-managed installs with copied skill files;
- routing multi-skill repos, single-skill repos, and AgentSkills-compatible repos to the right adapter;
- auditing a third-party skill repo before making it visible;
- resolving ambiguous phrases such as "install this skill repo", "use this skill pack", "add this GitHub skill", or "make these skills available".

Do not use this skill for writing new skill content. Use an authoring skill for that. Do not use it after the user already clearly requested one concrete runtime and the appropriate adapter skill is available.

## Routing dimensions

Resolve these before installation:

- **Target runtime:** the agent/platform that should load the skill.
- **Visibility scope:** shared/runtime-wide, one agent, workspace-local, project-local, runtime-private, or reference-only.
- **Ownership model:** Git-managed package, marketplace/registry install, copied local override, or temporary sandbox clone.
- **Trust level:** trusted, known-public, unknown, untrusted, or private.
- **Repo shape:** single skill, `skills/<name>/` multi-skill pack, nested package, or unknown layout.
- **Update model:** pinned ref, default branch tracking, manual pull, marketplace update, or no install.
- **Conflict risk:** duplicate skill names, precedence rules, allowlists, and existing local overrides.

## Default decision rules

Prefer a package-managed shared install when the user asks for skills to be available broadly, reusable across agents, or maintained from an upstream Git repo.

Prefer a workspace-local install only when the skill is intentionally bound to one workspace, project, or local policy.

Prefer a runtime-private install only when the user explicitly names that runtime or asks for a private/native install, such as "Codex-only", "Claude-only", or "for this one agent only".

Prefer an audit/reference-only pass when the repo is unknown, untrusted, unusually broad, contains executable scripts that have not been reviewed, or the user only asks whether it is useful.

Prefer a marketplace/registry workflow when the user names a first-class registry or the platform has a canonical install command for that exact source.

If the current session is clearly inside one platform and the user says "install it here" without naming another runtime, default to that platform's shared/package-managed mechanism, not to a hidden private folder.

Ask one concise scope question only when a wrong decision would create durable config churn, expose a repo to the wrong agent, or make private material visible beyond the intended boundary.

## Workflow

1. Identify the user's requested outcome, not just the command they mentioned.
2. Classify the target runtime and visibility scope.
3. Inspect enough metadata to classify the repo shape and risk before execution. Do not run repo scripts during routing.
4. Choose the adapter:
   - OpenClaw shared Git skill repo -> use the OpenClaw extraDir installer.
   - Explicit Codex-only/native-agent skill -> use that runtime's private installer.
   - Marketplace/registry source -> use that registry workflow.
   - Unknown or risky repo -> audit first, then ask before making it visible.
5. Hand off a short routing receipt to the adapter.

## Routing Receipt

Use this shape in the handoff or final answer:

```markdown
Routing decision:
- target runtime:
- visibility scope:
- install model:
- repo shape:
- trust/risk:
- chosen adapter:
- why:
- stop/ask condition:
```

## Trigger Eval Set

Should trigger:

- "Install this GitHub skill repo."
- "Can we add this skill pack to the agent?"
- "Should this be OpenClaw-wide or Codex-only?"
- "Make these external AgentSkills available."
- "Audit this third-party skill repo before using it."
- "Where should we install this repo so all agents can see it?"

Should not trigger:

- "Create a new skill for this workflow."
- "Update the wording inside this existing skill."
- "Run `openclaw skills install` for this ClawHub package."
- "Clone this unrelated code repository."
- "Use the already configured OpenClaw extraDir installer for this known OpenClaw repo."
