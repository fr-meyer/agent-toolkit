---
name: skill-creator
description: Use this skill when creating, refining, reviewing, or auditing an Agent Skill intended to be portable and shareable across agents. Apply it to scope definition, SKILL.md authoring, trigger descriptions, resource layout, progressive-disclosure decisions, and publication-quality checks.
---

# Skill Creator

## Goal

Create Agent Skills that are clear, portable, easy to trigger correctly, and worth sharing across different skills-compatible agents.

Treat **Agent Skills** as the source framework. When you are unsure about the specification, triggering, progressive disclosure, scripts, validation, or publishing choices, check **Agent Skills documentation first**. Prefer an available **Agent Skills MCP** or equivalent integrated doc search. If that is unavailable, use official Agent Skills documentation through a docs or web search tool.

## Default workflow

### 1. Define the skill boundary

Identify:
- the repeated task or workflow to generalize
- the user intents that should trigger the skill
- nearby tasks that should not trigger it
- the non-obvious knowledge, procedure, or assets the base agent lacks

Create **one coherent unit of work** per skill. If the request naturally splits into two separate jobs, split the skill.

### 2. Choose the smallest useful structure

Use only what is justified:
- `SKILL.md` — always required
- `scripts/` — for deterministic or repeatedly reused executable logic
- `references/` — for detailed material that should load only when needed
- `assets/` — for templates or static resources used in outputs

Default to the smallest structure that can do the job well.

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

### 5. Keep SKILL.md lean

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

### 6. Prefer defaults over menus

Pick a default approach. Mention alternatives only as fallbacks with clear conditions.

This reduces dithering and improves consistency across agents.

### 7. Add boundaries and gotchas

Call out:
- common mistakes
- non-obvious constraints
- naming mismatches
- portability traps
- adjacent tasks that should not use the skill

This section often matters more than extra explanation.

### 8. Evaluate before calling it finished

Create a small trigger eval set:
- should-trigger examples
- should-not-trigger near-misses

Vary phrasing, explicitness, detail level, and realism. Improve the description based on false positives and false negatives. Do not overfit to one phrase.

When evaluating this skill's own trigger behavior, read:
- `references/eval-prompts.json`

### 9. Audit for publication quality

When preparing a skill for publication, or when doing a stricter compliance review, read:
- `references/agent-skills-publication-checklist.md`

Use that file for final checks on structure, triggering, progressive disclosure, portability, and unnecessary clutter.

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
- Do not hardcode one host product unless explicitly requested.
- Do not stuff `SKILL.md` with reference material that is not always needed.
- Do not invent specification details when Agent Skills docs can be checked quickly.
- Do not add clutter files that do not help the agent perform the task.

## Final reminder

When uncertain, check **Agent Skills** first. Prefer the official specification and best-practice guidance over habit or platform-specific folklore. If an **Agent Skills MCP** is available, use it for targeted searches before making authoring or publication decisions.