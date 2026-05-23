---
name: recipe-knowledge-manager
description: Normalize, archive, index, and wiki/knowledge-base-link cooking recipes and culinary techniques. Use when the user shares recipe text, asks to save or remember a recipe, asks whether recipe notes should be integrated or separated, wants a normalized recipe template with a recipe card at the top, wants recipe indexes/wiki pages, wants sale/batch-friendly recipe cards, or wants recurring culinary rules/techniques consolidated across recipes.
---

# Recipe Knowledge Manager

## Goal

Turn messy recipe notes into durable, portable recipe knowledge: one clean recipe fiche per dish, a consistent recipe card at the top, integrated recipe-specific rules and tips, optional cross-recipe technique pages, an index entry, and wiki/knowledge-base-friendly synthesis when available.

## Quick Decision Rules

- **If the user asks to save/archive/remember a recipe:** act in this turn when a recipe root is discoverable.
- **If the user asks for a wiki or knowledge base:** keep source recipe files as the source of truth, then create/update navigation and synthesis pages.
- **If tips/rules apply only to one recipe:** integrate them into that recipe fiche.
- **If tips/rules apply across many recipes:** also maintain a separate technique page, but do not replace the per-recipe rules.
- **If the source is private pasted text:** preserve provenance as private user-provided text, not chat metadata.
- **If the source is a public page/book/video:** cite the source and summarize/normalize; avoid copying large blocks of protected prose verbatim.

## Portable Storage Resolution

Resolve storage from the first trusted source available:

1. Explicit user-provided destination.
2. Existing project recipe index or recipe folder.
3. Existing memory/wiki conventions in the workspace.
4. If no trusted destination exists, ask one concise question before writing.

Common layout when no stricter local convention exists:

```text
recipes/
├── recipe-index.md
├── YYYY-MM-DD-recipe-slug.md
└── techniques/
    └── technique-slug.md
```

If the host workspace already uses a memory folder, `memory/recipes/` is also acceptable. Do not hardcode either path as mandatory; treat storage as a discoverable/default convention.

## Workflow

### 1. Capture and classify

Identify:

- recipe name and variants
- source kind: user-pasted text, URL, video transcript, book note, own synthesis
- language
- portions/yield
- target texture/style
- constraints: vegan, gluten-free, equipment, time, budget
- whether the user wants only saving, normalization, comparison, or wiki creation

For private chat text, do not store sender labels, message IDs, or unrelated metadata.

### 2. Normalize into a recipe fiche

Use one file per executable recipe. Put the **Recipe card** immediately after the title so the file opens like a usable kitchen card. Put provenance/source trace near the end unless local conventions require otherwise. Use `references/recipe-template.md` as the default structure.

Keep the fiche kitchen-friendly:

- stable exact quantities over broad ranges
- steps in execution order
- temperatures and rest times explicit
- sensory cues included when useful
- golden rules and mistakes integrated near the end
- variants clearly separated from the main recipe

If the user provided multiple variants, either:

- create one consolidated fiche with named variants, or
- split into one fiche per executable recipe when each variant has different ingredients/steps.

Prefer splitting when the user may cook them independently.

### 3. Handle rules, tips, and techniques

Use this retention pattern:

- **Recipe-specific rules:** include under `## Golden Rules / Règles d’or` in the recipe fiche.
- **Recipe-specific tips:** include under `## Astuces` / `## Tips`.
- **General technique repeated across recipes:** create or update a technique page such as `techniques/cookies-regles-dor.md`.
- **Index:** add tags that expose the techniques: `repos au froid`, `sous-cuisson`, `beurre pommade`, `insert congelé`, etc.

Avoid scattering a recipe into many files unless the files have a clear purpose. A user should be able to cook from one recipe fiche without opening a separate rules file.

### 4. Update the recipe index

Maintain a compact index entry per recipe:

```md
- **Recipe title**
  - source/context: <short provenance>
  - portions: <yield>
  - tags: <comma-separated searchable tags>
  - note: <one-line practical note>
  - file: `<relative path>`
```

For large collections, add category sections or companion index pages rather than making the primary index unreadable.

### 5. Create or refresh a wiki/knowledge base when requested

When a wiki or knowledge-base system is available:

1. Identify the available implementation and its update workflow.
2. For OpenClaw memory wiki, check `openclaw wiki status`.
3. If OpenClaw bridge mode is enabled and latest memory files matter, run `openclaw wiki bridge import` or ingest the relevant files.
4. Create/update synthesis pages for navigation, not as the only source of truth.
5. Compile/lint when the implementation supports it, e.g. `openclaw wiki compile` then `openclaw wiki lint`.

Recommended wiki pages:

- `Recettes — Index général`
- category pages: `Cookies`, `Desserts`, `Sauces`, etc.
- technique pages: `Techniques cookies`, `Caramel`, `Meringue`, etc.
- ingredient pages when useful: `Pistache`, `Crème de marrons`, `Caramel beurre salé`

Keep wiki claims source-backed with links to recipe files or daily notes.

### 6. Verify before replying

Before claiming completion, verify:

- recipe file exists
- recipe card is at the top
- rules/tips are integrated or intentionally linked
- index entry points to the right file
- wiki/knowledge-base compile/lint ran if supported and updated
- no personal chat metadata, sender labels, message IDs, local usernames, or secrets were stored
- daily trace exists if the local memory convention uses daily logs

## Quality Bar

A normalized recipe should answer at a glance:

- What is it?
- How many portions?
- How long does it take?
- What texture/result are we aiming for?
- What exact quantities should I use?
- What are the non-negotiable rules?
- What should I avoid?
- Where did this note come from?

## Reference

- Use `references/recipe-template.md` for the canonical recipe fiche template and example sections.
