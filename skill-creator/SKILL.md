---
name: skill-creator
description: Use this skill when creating, drafting, reviewing, refining, or auditing an Agent Skill that should be generalizable, portable, and shareable across agents and products. Apply it when the task is to define scope, write or improve SKILL.md, choose triggers, design scripts/references/assets, test activation quality, or turn an ad hoc workflow into a reusable Agent Skill. Prefer this skill for public or shared skills rather than one-off local helpers.
compatibility: Best with agents that can read/write files and search Agent Skills documentation via MCP or an equivalent docs/web search tool.
---

# Skill Creator

## Goal

Create Agent Skills that are portable, coherent, concise, and genuinely reusable across different skills-compatible agents.

Treat **Agent Skills** as the source framework. When questions arise about the specification, frontmatter fields, triggering, progressive disclosure, scripts, or validation, consult the **Agent Skills documentation first**, preferably through an available **Agent Skills MCP** integration or an equivalent docs/search tool. If MCP is unavailable, use the official Agent Skills docs via web/doc search.

## Core principles

1. **Create one coherent unit of work per skill.**
   - Make the skill broad enough to be reusable.
   - Do not make it so broad that it becomes a vague catch-all.

2. **Optimize for sharing across agents.**
   - Prefer agent-agnostic instructions.
   - Avoid product-specific assumptions unless truly required.
   - Avoid local machine assumptions, hardcoded absolute paths, personal context, and hidden dependencies.

3. **Keep the trigger sharp.**
   - The `description` field is the primary activation mechanism.
   - Describe both what the skill does and when it should be used.
   - Focus on user intent, not internal implementation.

4. **Use progressive disclosure.**
   - Keep `SKILL.md` lean and useful on every activation.
   - Move bulky details into `references/`.
   - Move deterministic reusable logic into `scripts/`.
   - Put templates or static files into `assets/` only when needed.

5. **Prefer defaults over menus.**
   - Pick a default method or tool.
   - Mention alternatives only as fallbacks.
   - Reduce agent dithering.

6. **Teach a reusable procedure, not a single answer.**
   - Explain how to approach the class of tasks.
   - Do not overfit to one specific request.

7. **Refine from real use.**
   - Turn real corrections, failures, and edge cases into better instructions, gotchas, and trigger boundaries.

## Always consult Agent Skills docs when needed

Consult Agent Skills documentation when any of the following is unclear:
- valid frontmatter fields
- naming constraints
- description/trigger wording
- portability and compatibility requirements
- progressive disclosure and file layout
- scripts and dependency patterns
- validation or packaging expectations

Preferred order:
1. Agent Skills MCP or equivalent integrated doc search
2. Local or mirrored Agent Skills documentation
3. Official Agent Skills website/search

Do not guess when the specification or best practice can be checked quickly.

## Authoring workflow

### 1. Understand the target skill through real use

Before drafting, identify:
- the repeated task or workflow to generalize
- concrete examples of requests that should trigger the skill
- nearby requests that should **not** trigger it
- what domain knowledge or procedure the base agent would likely miss

If the request is underspecified, ask for only the minimum extra examples needed.

### 2. Define the skill boundary

Answer these questions before writing:
- What is the single coherent job of this skill?
- What user intents should trigger it?
- What adjacent jobs are out of scope?
- What assumptions must remain portable across agents?
- What part should be procedural guidance vs script/reference material?

If the scope feels like two separate skills, split it.

### 3. Choose the smallest useful structure

Use only the directories that earn their keep:
- `SKILL.md` — always required
- `scripts/` — only for deterministic or repeated executable logic
- `references/` — only for detailed material that should load on demand
- `assets/` — only for templates or static resources used in output

Do not add extra housekeeping documents unless they directly help agents perform the task.

### 4. Draft frontmatter carefully

Use valid Agent Skills frontmatter.

Minimum portable pattern:

```yaml
---
name: skill-name
description: Use this skill when ...
---
```

Frontmatter rules to respect:
- `name` must match the folder name
- use lowercase letters, digits, and hyphens only
- keep the name short and clear
- keep the description concise but specific
- prefer minimal frontmatter unless optional fields are genuinely helpful

### 5. Write the description for triggering

Write the description so an agent can decide to load the skill.

Include:
- the core job the skill performs
- the user intents or contexts that should trigger it
- common phrasings or adjacent contexts when helpful
- boundaries when false positives are likely

Good description pattern:

```text
Use this skill when the user needs <coherent job>, especially for <common contexts>. Apply it when requests involve <intent A>, <intent B>, or <intent C>, even if the user does not use those exact terms. Do not use it for <near-miss or out-of-scope cases>.
```

Bad patterns:
- overly vague: `Helps with files.`
- overly broad: `Use for anything related to software.`
- implementation-led instead of intent-led

### 6. Write a lean SKILL.md body

Keep the main file focused on what the agent should know every time the skill activates.

Recommended sections:
- Goal
- Core workflow
- Default approach
- Scope boundaries
- Inputs to confirm
- Procedure
- Gotchas
- Output format
- Resources
- Portability notes

Keep detailed examples, API notes, long schemas, and exhaustive edge cases out of the main file unless they are essential on every run.

### 7. Add resources intentionally

#### Use `scripts/` when:
- the same code would otherwise be rewritten repeatedly
- reliability and repeatability matter
- the task benefits from deterministic behavior

Script rules:
- avoid interactive prompts
- accept flags, stdin, or environment variables
- support `--help`
- print helpful error messages
- prefer structured output for machine use
- avoid hidden environment assumptions
- pin external versions when appropriate

#### Use `references/` when:
- detailed context is needed only sometimes
- the skill covers multiple variants or domains
- large docs would bloat `SKILL.md`

Reference rules:
- tell the agent exactly **when** to read each file
- keep references one level deep from `SKILL.md`
- avoid deep reference chains

#### Use `assets/` when:
- the skill needs templates or static resources in the produced output

### 8. Add boundaries and gotchas

Include a short list of:
- common mistakes
- non-obvious constraints
- naming mismatches
- environmental traps
- adjacent tasks that should not use the skill

This section often provides the highest value.

### 9. Evaluate trigger quality

Create a small eval set before calling the skill complete.

Include:
- 8-10 should-trigger examples
- 8-10 should-not-trigger near-misses

Vary:
- phrasing
- explicitness
- detail level
- realistic file/context mentions
- casual wording and typos when appropriate

Revise the `description` based on false negatives and false positives. Improve generalization; do not keyword-stuff for one narrow test case.

### 10. Validate and iterate

If the current environment has Agent Skills validation or packaging tools, use them.
If not, still check manually that:
- frontmatter is valid
- the folder and `name` match
- descriptions are precise
- file references are relative and clear
- only necessary files are included

Then iterate after real usage.

## Output standard for this skill

When using this skill to create or revise another skill, produce:
1. the proposed skill name
2. a one-sentence scope statement
3. a trigger description draft
4. the recommended directory structure
5. the `SKILL.md` draft
6. any bundled scripts/references/assets that are justified
7. a short list of should-trigger and should-not-trigger eval prompts
8. a note on portability risks, if any

## Reusable creation template

Use this skeleton as the default starting point for new shareable skills:

````markdown
---
name: <skill-name>
description: Use this skill when the user needs <core job>, especially for <common trigger contexts>. Apply it when requests involve <intent A>, <intent B>, or <intent C>, even if the user does not use those exact terms. Do not use it for <out-of-scope cases>.
---

# <Readable Skill Title>

## Goal

Help the agent perform <coherent class of tasks> in a portable, repeatable way across environments.

## Core workflow

1. Identify whether the request is in scope.
2. Gather the minimum required inputs.
3. Use the default approach unless a listed exception applies.
4. Produce output in the expected format.
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

## Inputs to confirm

- `<required input 1>`
- `<required input 2>`
- `<required constraint or preference>`

## Procedure

### 1. Inspect
- Determine `<decision point>`
- Check `<precondition>`
- Note `<important context>`

### 2. Execute
- Apply `<default method>`
- Switch to `<fallback>` only when `<condition>`
- Keep the process minimal and deterministic

### 3. Validate
- Verify `<output property 1>`
- Verify `<output property 2>`
- Retry once with a specific correction if validation fails

## Gotchas

- `<non-obvious fact 1>`
- `<non-obvious fact 2>`
- `<edge case or mismatch 3>`

## Output format

Return:
- `<artifact/file/output>`
- `<summary/explanation>`
- `<warning or confidence note if needed>`

## Resources

Read only when needed:
- `references/<topic>.md` — use when `<condition>`
- `references/<topic>.md` — use when `<condition>`

Run only when needed:
- `scripts/<script-name>` — use for `<task>`
- `scripts/<script-name>` — use for `<task>`

## Portability notes

- Use relative paths from the skill root.
- Avoid product-specific assumptions unless explicitly required.
- Prefer stable, version-pinned external commands.
- Do not rely on interactive prompts.
````

## Quality bar

A good output from this skill should produce a new skill that is:
- clearly scoped
- easy to trigger correctly
- lean in its default context footprint
- reusable across agents
- explicit about defaults and boundaries
- easy to refine after real usage

## Do not do these things

- Do not write a catch-all skill with fuzzy scope.
- Do not hardcode one host product unless the user explicitly wants that.
- Do not pack detailed reference material into the main `SKILL.md` unless it is always needed.
- Do not rely on interactive scripts.
- Do not invent specification details when Agent Skills docs can be checked.
- Do not add clutter files that do not help the agent perform the task.

## Final reminder

When uncertain, check **Agent Skills** first. Prefer the official specification and best-practice guidance over habit, guesswork, or platform-specific folklore. If an **Agent Skills MCP** is available, use it for targeted searches before making format or authoring decisions.