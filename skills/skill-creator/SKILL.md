---
name: skill-creator
description: Use this skill when creating, updating, modernizing, refining, reviewing, or auditing an Agent Skill intended to be portable and shareable across agents. Apply it to scope definition, SKILL.md authoring, trigger descriptions, resource layout, progressive-disclosure decisions, publication-quality checks, and minimal justified updates to existing skills.
---

# Skill Creator

## Goal

Create Agent Skills that are clear, portable, easy to trigger correctly, and worth sharing across different skills-compatible agents.

Treat **Agent Skills** as the source framework. Use the **online Agent Skills source first**: prefer **Agent Skills MCP** before relying on bundled or local skill documentation. If Agent Skills MCP is not accessible, use the public Agent Skills website (`https://agentskills.io/home`, plus the relevant documentation pages under that site) or the GitHub repository (`https://github.com/agentskills/agentskills`) as the fallback source of truth. Treat the current skill files as secondary guidance that may lag behind the latest Agent Skills resources. If the online source shows that local skill-creator guidance is outdated or incorrect, update the local files directly.

## Required preconditions

Before starting any create, update, review, or audit work with this skill, confirm all of the following:
- the folder where the skill should be saved or edited has already been specified explicitly at least once, or is available from trusted memory/session context
- at least one current Agent Skills reference source is accessible: prefer **Agent Skills MCP**, but otherwise use the Agent Skills website (`https://agentskills.io/home` and its relevant documentation pages) or the GitHub repository (`https://github.com/agentskills/agentskills`)
- an Agent Skills validation CLI is executable in the current environment: prefer `agentskills`, but accept `skills-ref` when that is the exposed command name in the current environment
- the current skill library can be inspected so similar or overlapping skills can be checked before creating or updating anything
- if the skill is intended for the shared/reusable skill repo, the target repo root must be known from trusted context and the work must start from that repo's `dev` branch on a fresh branch created for the specific skill

If any of these requirements are not satisfied:
- do not start or continue the work
- do not create or modify skill files yet
- tell the user exactly which requirement is missing
- explain clearly why the work is blocked
- say what needs to be provided or fixed before proceeding
- do not claim Agent Skills validation unless `agentskills validate` or `skills-ref validate` actually ran successfully in the current environment

## Default workflow

### 1. Audit the existing skill library first

Before designing or revising a skill, inspect the current skill library for similar, overlapping, or adjacent skills.

Identify:
- exact or near-duplicate skills
- broader parent skills that already cover most of the requested scope
- narrower reusable sub-skills that could be referenced instead of reimplemented
- gaps where no existing skill is a good fit

Default decision order:
1. reuse an existing skill if it already fits
2. update or extend an existing skill if that is cleaner than creating a parallel one
3. split the proposal into multiple reusable skills if the requested scope contains multiple coherent sub-workflows
4. create a brand-new standalone skill only when the above options are clearly worse

### 1.25 Shared-repo branch rule

When creating a shared/reusable skill in the shared skills repository:
- start from the repo's `dev` branch
- create a dedicated branch per skill before editing files
- do not create shared skills directly on `main`
- keep the branch name specific to the skill being created

### 1.5 Check whether the scope should be split

Before finalizing a new skill or an update, evaluate whether the proposed scope is too broad.

Split the design when:
- the workflow contains multiple reusable sub-tasks with distinct triggers
- one part mainly audits while another part remediates or executes
- one part is a reusable utility that could support multiple other skills
- keeping everything in one skill would make triggering fuzzier or instructions heavier

Prefer:
- smaller coherent reusable skills
- explicit delegation/interconnection between skills
- one orchestrator skill only when coordination logic truly needs to stay centralized

### 2. Choose the smallest useful structure

Use only what is justified:
- `SKILL.md` — always required
- `scripts/` — for deterministic or repeatedly reused executable logic
- `references/` — for detailed material that should load only when needed
- `assets/` — for templates or static resources used in outputs

Default to the smallest structure that can do the job well.

Also prefer the smallest **skill boundary** that can do the job well:
- do not create a duplicate when an existing skill already fits
- do not keep unrelated reusable sub-workflows bundled together just because they appeared in the same conversation
- do not create a new orchestrator when direct reuse of an existing skill is sufficient

If the folder where the new skill should be saved is not explicit and is not available from trusted memory or session context, stop and ask the user which folder should receive the skill before creating files.

### 3. Write minimal valid frontmatter

Default to this pattern:

```yaml
---
name: skill-name
description: Use this skill when ...
---
```

Rules:
- `name` must match the folder name
- use lowercase letters, digits, and hyphens only
- keep the description intent-led and specific
- add optional frontmatter fields only when they materially help portability, licensing clarity, or environment requirements

Do not add fields just because they are available.

### 4. Write the description for triggering

The description is the primary activation mechanism. Write it around **user intent**, not internal implementation.

Include:
- the core job the skill performs
- common contexts or user requests that should trigger it
- useful boundary language when false positives are likely

Good pattern:

```text
Use this skill when the user needs <coherent job>, especially for <common contexts>. Apply it when requests involve <intent A>, <intent B>, or <intent C>, even if the user does not use those exact terms. Do not use it for <out-of-scope cases>.
```

Bad patterns:
- vague: `Helps with files.`
- too broad: `Use for anything related to software.`
- implementation-led instead of intent-led

### 5. Update existing skills carefully

When editing an existing skill:
- inspect the current `SKILL.md` and bundled files first
- inspect nearby skills in the current skill library before deciding the update boundary
- use Agent Skills MCP as the primary source of truth when available
- if Agent Skills MCP is unavailable, use the Agent Skills website or GitHub repository as the fallback source of truth
- identify what is outdated, incorrect, redundant, missing, duplicated, or better owned by another skill
- prefer the smallest justified edit set
- preserve the current skill name, folder, and scope unless a clear problem requires changing them
- if the best fix is to delegate part of the workflow to another existing or newly extracted skill, prefer that over bloating the current skill
- if the online Agent Skills source shows that local skill files are outdated or incorrect, update the local files directly
- if the Agent Skills validator is available, run `agentskills validate path/to/skill`
- if the current environment exposes the older or alternate command name instead, run `skills-ref validate path/to/skill`
- report what changed, why it changed, what was intentionally left unchanged, whether similar existing skills were considered, and whether validation succeeded

### 6. Keep SKILL.md lean

Put only always-needed guidance in the main file.

Keep in `SKILL.md`:
- goal and scope
- default workflow
- defaults and fallbacks
- key gotchas
- output expectations
- clear directions for when to read support files

Move to `references/` when content is mainly for:
- audits
- publication review
- variant-specific details
- long checklists
- schemas or deep reference material

Move to `scripts/` when behavior should be deterministic and reusable.

### 7. Prefer defaults over menus

Pick a default approach. Mention alternatives only as fallbacks with clear conditions.

This reduces dithering and improves consistency across agents.

### 8. Add boundaries and gotchas

Call out:
- common mistakes
- non-obvious constraints
- naming mismatches
- portability traps
- adjacent tasks that should not use the skill

This section often matters more than extra explanation.

### 9. Evaluate before calling it finished

Create a small trigger eval set:
- should-trigger examples
- should-not-trigger near-misses

Vary phrasing, explicitness, detail level, and realism. Improve the description based on false positives and false negatives. Do not overfit to one phrase.

When evaluating this skill's own trigger behavior, read:
- `references/eval-prompts.json`

When reviewing this skill's output quality after it triggers, read:
- `references/output-quality-eval.json`

### 10. Audit for publication quality

When preparing a skill for publication, or when doing a stricter compliance review, read:
- `references/agent-skills-publication-checklist.md`

Use that file for final checks on structure, triggering, progressive disclosure, portability, and unnecessary clutter.

If an Agent Skills validator is available, run a final validator pass:
- preferred: `agentskills validate path/to/skill`
- alternative when that is the exposed command name in the current environment: `skills-ref validate path/to/skill`

If neither validator command was run, or the available one could not be used successfully, explicitly say so in the output and explain why validation was not possible.

## Rules for bundled resources

### `scripts/`

Add a script only when it meaningfully improves reliability or prevents repeated code generation.

Script requirements:
- do not rely on interactive prompts
- accept flags, stdin, or environment variables
- provide `--help`
- print helpful errors
- prefer structured output when possible
- avoid hidden environment assumptions
- pin external versions when appropriate

### `references/`

Add references only when they reduce context bloat in `SKILL.md`.

Current references in this skill:
- `references/agent-skills-publication-checklist.md` — read when preparing a skill for publication or doing a stricter compliance review
- `references/eval-prompts.json` — read when testing whether `skill-creator` triggers on the right requests
- `references/output-quality-eval.json` — read when checking whether `skill-creator` produces complete, publication-ready outputs after it triggers

Reference requirements:
- say exactly when to read each file
- keep references one level deep from `SKILL.md`
- avoid deep chains of references

### `assets/`

Add assets only when the skill genuinely needs templates or static resources in produced outputs.

## Output requirements

When using this skill to create or revise another skill, produce:
1. the proposed skill name
2. a one-sentence scope statement
3. the trigger description draft
4. the recommended directory structure
5. the `SKILL.md` draft
6. any justified `scripts/`, `references/`, or `assets/`
7. a short set of should-trigger and should-not-trigger eval prompts
8. portability risks or publication concerns, if any
9. the validation status, including whether `agentskills` or `skills-ref` was run and, if not, why validation was not possible
10. for update tasks, a change summary describing what was updated, what was intentionally left unchanged, and why
11. a similarity-check summary stating which existing skills were reviewed, which ones were considered relevant, and why they were reused, extended, rejected, or delegated to
12. a scope-splitting decision stating whether the proposed work should remain one skill or be split into multiple reusable skills, and why
13. if work could not start or continue because a prerequisite was missing, a clear blocked-status explanation naming the missing requirement and why it prevented the work

## Starter template

Use this as the default starting point:

````markdown
---
name: <skill-name>
description: Use this skill when the user needs <core job>, especially for <common contexts>. Apply it when requests involve <intent A>, <intent B>, or <intent C>, even if the user does not use those exact terms. Do not use it for <out-of-scope cases>.
---

# <Readable Skill Title>

## Goal

Help the agent perform <coherent class of tasks> in a portable, repeatable way across environments.

## Workflow

1. Confirm the request is in scope.
2. Gather the minimum required inputs.
3. Use the default approach unless a listed exception applies.
4. Produce the expected output.
5. Validate before finishing.

## Default approach

- Use: `<default method/tool>`
- Fallback: `<fallback>` only when `<condition>`
- Avoid: `<common anti-pattern>`

## Scope boundaries

Use this skill for:
- `<in-scope task 1>`
- `<in-scope task 2>`
- `<in-scope task 3>`

Do not use this skill for:
- `<near-miss 1>`
- `<near-miss 2>`
- `<adjacent but separate domain>`

## Procedure

### Inspect
- Determine `<decision point>`
- Check `<precondition>`
- Note `<important context>`

### Execute
- Apply `<default method>`
- Switch to `<fallback>` only when `<condition>`

### Validate
- Verify `<output property 1>`
- Verify `<output property 2>`

## Gotchas

- `<non-obvious fact 1>`
- `<non-obvious fact 2>`
- `<edge case or mismatch 3>`

## Resources

Read only when needed:
- `references/<topic>.md` — use when `<condition>`

Run only when needed:
- `scripts/<script-name>` — use for `<task>`

## Portability notes

- Use relative paths from the skill root.
- Avoid product-specific assumptions unless explicitly required.
- Do not rely on interactive prompts.
````

## Do not do these things

- Do not create a fuzzy catch-all skill.
- Do not create a duplicate or near-duplicate skill before checking the current skill library.
- Do not ignore an existing skill that should be reused, extended, or explicitly referenced instead.
- Do not keep multiple reusable sub-workflows bundled together when they should be split into smaller interoperable skills.
- Do not hardcode one host product unless explicitly requested.
- Do not stuff `SKILL.md` with reference material that is not always needed.
- Do not invent specification details when Agent Skills docs can be checked quickly.
- Do not add clutter files that do not help the agent perform the task.

## Final reminder

When uncertain, check **Agent Skills** first. Prefer the official specification and best-practice guidance over habit or platform-specific folklore. If an **Agent Skills MCP** is available, use it for targeted searches before making authoring or publication decisions. If MCP is unavailable, use the public Agent Skills website or the GitHub repository instead of relying only on local copies.