# Agent Skills Publication Checklist

Read this file when:
- preparing a skill for publication or sharing
- auditing an existing skill for Agent Skills alignment
- reviewing portability, trigger quality, or progressive-disclosure hygiene

Use this checklist after drafting the main skill.

Before relying on local guidance, prefer the current online Agent Skills source through MCP or equivalent docs search. If the online source conflicts with local skill files, trust the up-to-date online source and update the local files.

## 1. Basic format

Confirm:
- the skill folder contains `SKILL.md`
- the `name` in frontmatter exactly matches the folder name
- `name` uses lowercase letters, digits, and hyphens only
- the frontmatter is valid YAML
- `description` is present and non-empty
- optional frontmatter fields are included only when justified

Default publication posture:
- prefer only `name` and `description`
- add `license` when distribution terms need to be explicit
- add `compatibility` only when the environment requirements are materially important

## 2. Scope quality

Confirm:
- the skill covers one coherent unit of work
- the scope is broad enough to be reusable
- the scope is not so broad that it becomes a vague catch-all
- adjacent out-of-scope tasks are clear

Warning signs:
- the skill sounds like a general assistant role
- the skill bundles unrelated workflows
- the skill exists mainly to restate generic advice the base agent already knows

## 3. Trigger quality

Confirm:
- the description is intent-led, not implementation-led
- it says both what the skill does and when to use it
- it includes useful context words or task patterns without keyword stuffing
- it avoids false-triggering on obvious neighboring tasks

Test with examples:
- 8-10 should-trigger prompts
- 8-10 should-not-trigger near-misses

Improve the description if:
- valid prompts fail to trigger
- neighboring prompts trigger too often

## 4. Progressive disclosure

Confirm:
- `SKILL.md` contains only guidance that is useful on every activation
- deep detail has been moved to `references/` when appropriate
- deterministic repeated logic has been moved to `scripts/` when appropriate
- templates or static resources live in `assets/` only when justified
- support files are linked directly from `SKILL.md`
- support files are one level deep from `SKILL.md`

Warning signs:
- `SKILL.md` reads like a long manual
- reference files exist but `SKILL.md` never says when to read them
- the skill contains multiple nested documentation layers

## 5. Resource quality

### Scripts

Confirm:
- scripts are non-interactive
- scripts document usage clearly, ideally with `--help`
- inputs come from flags, stdin, or environment variables
- errors are actionable
- outputs are structured when practical
- version-sensitive external tools are pinned when appropriate

### References

Confirm:
- each reference file has a clear purpose
- each reference file is read conditionally, not by default
- detailed material is not duplicated between `SKILL.md` and `references/`

### Assets

Confirm:
- assets are actually used by the skill
- assets are not just extra samples or decorative files

## 6. Portability

Confirm:
- instructions are agent-agnostic unless product specificity is intentional
- no hardcoded personal paths are required for normal use
- no private local context is assumed
- no hidden dependencies are required without being stated
- commands and file references use portable, explicit conventions

Warning signs:
- the skill only makes sense inside one author's machine setup
- the instructions assume a particular chat product or internal tool without explanation
- the skill depends on tribal knowledge not written anywhere

## 7. Output quality

Confirm the skill helps the agent produce:
- a clear result
- minimal but sufficient explanation
- appropriate validation or confidence notes
- consistent structure across similar tasks

## 8. Clutter check

Remove files that do not materially help the agent do the job.

Typical anti-patterns:
- extra documentation folders with no execution value
- duplicated instructions across multiple files
- placeholder examples that were never replaced
- environment-specific leftovers from development

## 9. Final release decision

If `skills-ref` is available, run:
- `skills-ref validate path/to/skill`

If `skills-ref` was not run, or could not be used, say that explicitly in the output and explain why validation was not possible.

A skill is ready to share when it is:
- valid
- coherent
- easy to trigger correctly
- lean in default context cost
- explicit about boundaries
- portable across agents or clearly scoped when not portable
- easy to refine after real use

If any of those are weak, tighten the skill before publishing.