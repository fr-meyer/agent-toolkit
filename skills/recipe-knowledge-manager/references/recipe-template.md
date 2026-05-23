# Recipe Fiche Template

Use this template for normalized recipe files. Keep the recipe card immediately after the title so the user can quickly decide whether to cook, scale, store, or sell it.

```md
# <Recipe title>

## Recipe card

- **Type:** <dessert, sauce, bread, main, etc.>
- **Yield:** <servings / pieces / batch weight>
- **Batch yield:** <optional: total pieces/weight for production batches>
- **Active time:** <time>
- **Total time:** <time incl. rest/freezing>
- **Difficulty:** <easy | medium | advanced>
- **Target result:** <texture/flavor/style>
- **Oven / heat:** <temperature and mode>
- **Rest / cold time:** <time>
- **Equipment:** <optional>
- **Make-ahead:** <optional>
- **Storage / shelf life:** <optional>
- **Allergens:** <optional: gluten, egg, milk, nuts, sesame, etc.>
- **Packaging:** <optional: bag, box, label, transport notes>
- **Cost / sale note:** <optional: cost per piece or suggested pricing note>
- **Tags:** <comma-separated tags>

---

## Summary

<2-5 sentence practical overview.>

## Ingredients

### Main component
- <quantity> <ingredient>

### Filling / topping / finish
- <quantity> <ingredient>

## Method

1. <Step in execution order.>
2. <Step with sensory cue.>
3. <Step with temperature/time.>

## Golden Rules / Règles d’or

- **Rule:** why it matters.
- **Rule:** why it matters.

## Tips

- <Practical tip.>
- <Substitution or make-ahead note.>

## Variants

- **Variant name:** <what changes and why.>

## Mistakes to avoid

- **Mistake:** consequence and fix.

## Serving / reheating

- <Best serving temperature, reheating cue, pairing.>

## Source notes

- Date captured: <YYYY-MM-DD HH:mm timezone>
- User intent: <what the user asked>
- Source kind: <pasted text | URL | video transcript | book note | original synthesis>
- Source locator: <URL or private user-provided text; avoid chat IDs unless needed>
- Access/resolution status: <resolved | partial | blocked>
- Language: <language>
- Privacy/sensitivity notes: <if any>
- Related files:
  - `<path>`
- Attribution/uncertainty notes: <source caveats, “private user-provided text,” or unverified attribution>
```

## Recipe card field guidance

- **Type:** Prefer useful categories over strict taxonomy: cookies, tart, cake, sauce, drink, fermentation, pasta, etc.
- **Yield:** Include both count and weight when known, e.g. “12 cookies of 60 g”.
- **Batch yield:** Use when the user is producing for resale, gifting, events, or meal prep.
- **Active time vs total time:** Total includes chilling, proofing, freezing, marinating, or overnight rest.
- **Target result:** Make the desired sensory outcome explicit: chewy center, crisp edge, runny center, glossy meringue, stable emulsion.
- **Oven / heat:** Include mode if relevant: convection/fan, static, stovetop, bain-marie.
- **Rest / cold time:** Mark non-negotiable rest times.
- **Make-ahead:** Use for chilling/freezing/advance-prep instructions.
- **Storage / shelf life:** Include food-safe practical storage notes when known.
- **Allergens:** Useful when recipes may be shared or sold; include only likely allergens from ingredients.
- **Packaging:** Useful for bake sales, markets, gifts, or transport.
- **Cost / sale note:** Optional; avoid pretending exact margins are known when ingredient prices are missing.
- **Tags:** Include ingredients, techniques, texture, equipment, and dietary constraints.

## Normalization rules

- Prefer exact quantities and one recommended method over broad ranges.
- Preserve meaningful variants, but do not let variants obscure the main executable recipe.
- Move long theory into tips or technique pages.
- Keep critical failure points in `Mistakes to avoid`.
- If an auto-transcript/source is noisy, mark uncertainty plainly.
- If attribution is unverified, say so: “inspiration claimed in source text; not independently verified.”
- Do not store personal chat metadata, sender labels, message IDs, local usernames, or unrelated private context.

## Example recipe card

```md
## Recipe card

- **Type:** cookies
- **Yield:** 12 cookies of 55-60 g
- **Batch yield:** scale by multiplying dough-ball count; keep dough balls the same weight
- **Active time:** 20 min
- **Total time:** 2 h 35 min
- **Difficulty:** easy-medium
- **Target result:** thick cookies, crisp edges, chewy center, strong pistachio flavor
- **Oven / heat:** 170°C fan, 12-14 min
- **Rest / cold time:** 2 h minimum
- **Equipment:** mixing bowl, spatula, baking tray, scale
- **Make-ahead:** dough balls freeze well
- **Storage / shelf life:** 3 days airtight; refresh briefly in warm oven if needed
- **Allergens:** gluten, egg, milk, nuts
- **Packaging:** paper bag or clear cookie sleeve after full cooling
- **Cost / sale note:** calculate from local ingredient prices before setting sale price
- **Tags:** cookies, pistachio, chocolate, cold rest, underbaking, beurre pommade
```
