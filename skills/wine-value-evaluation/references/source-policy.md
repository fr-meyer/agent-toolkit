# Wine source policy and provider caveats

## Identity and origin sources

Use these before quality scoring. A good value score is meaningless if the bottle identity is wrong.

Preferred identity sources:

1. Producer official page or technical sheet.
2. Importer/distributor page with label image and product metadata.
3. Appellation/region authority page when available.
4. Merchant page with clear label image, vintage, bottle size, and producer/cuvée details.
5. Wine database page only if it clearly matches producer, cuvée, vintage, and size.

For origin verification, confirm the full origin hierarchy separately: country, region, appellation/designation (AOC, DOC/DOCG, DO/DOCa, AVA, GI, etc.), producer, cuvée, grape/variety, and vintage. Do not infer origin from grape alone.

## Price sources

Default to prices from the wine’s country-of-origin market. This is the first benchmark because it estimates what the same bottle costs closest to its normal domestic distribution market.

Examples:

- Alsace, Bordeaux, Burgundy, Champagne → France benchmark first.
- Barolo, Chianti, Etna → Italy benchmark first.
- Rioja, Ribera del Duero, Priorat → Spain benchmark first.
- Napa, Oregon, Finger Lakes → US benchmark first.
- Mendoza → Argentina benchmark first.
- Marlborough → New Zealand benchmark first.

Use a user-requested benchmark market only as an override or secondary comparison. Use broader regional/global benchmarks only when origin-country evidence is weak.

Useful price sources include:

- Wine-Searcher market listings, filtered to the origin country when possible.
- Major retailers in the origin country.
- Producer shop or domestic importer/distributor recommended retail price when available.
- Specialist merchants in the origin country with current availability.
- Auction/secondary-market data only for rare wines; include buyer fees and mark confidence.

Normalize all prices:

- per 750 ml bottle unless comparing another standard size
- per bottle for bundles/cases
- after mandatory fees when known
- excluding optional shipping unless shipping is unavoidable and known
- with a dated currency conversion when comparing markets

Avoid using obviously stale, out-of-stock, cross-border, gray-market, or mismatched-vintage listings as primary evidence. If the origin-country market has too little data, name the fallback benchmark explicitly and lower confidence.

For non-vintage wines, multi-vintage blends, or formats other than 750 ml, match by exact label, lot/NV status, bottle size, and pack size. Do not invent a vintage match when the wine is intentionally non-vintage.

## Quality/review sources

Aim for at least 3 providers when possible. Mix critic and community sources.

### Community sources

- **Vivino**: useful broad sentiment and accessibility. Weight depends heavily on number of ratings. Beware wrong vintages merged under one listing, label confusion, and popularity bias.
- **CellarTracker**: useful for wine-enthusiast tasting notes. Stronger when there are multiple recent notes for the exact vintage. Beware tiny sample sizes.

### Aggregators and market databases

- **Wine-Searcher**: useful for price and sometimes critic/community summaries. Verify exact vintage and country filter.
- **Wine-Searcher professional/critic data** may be paywalled; do not bypass access controls.

### Expert/critic sources

- **Guide Hachette des Vins**: useful for French wines, especially awards/stars and qualitative tasting notes. Convert to numeric score only if necessary and disclose mapping.
- **La Revue du Vin de France (RVF)**: strong for French producer/cuvée quality context when accessible.
- **Decanter**: useful for English-language critic scores and regional tastings.
- **Jancis Robinson**: useful for expert 20-point scores and notes; often paywalled.
- **Wine Advocate / Robert Parker**, **Wine Enthusiast**, **James Suckling**, **Vinous**: use when the exact wine/vintage appears; many entries may be paywalled.

### Retailer reviews

Retailer ratings and tasting notes can support style fit and availability, but should receive lower weight than independent critic/community sources. Retailer descriptions are not independent quality evidence.

### Producer/importer claims

Use producer/importer materials for identity, technical facts, style, farming, vinification, and pairing notes. Do not count them as independent review quality.

## Handling sparse evidence

If a wine has few or no reviews:

- Use producer reputation and appellation/cuvée context as qualitative support only.
- Lower confidence rather than inventing a score.
- Consider ranking it separately as “promising but under-reviewed.”
- Explain whether it may still be a good gift due to producer recognition or style fit.

## Output citation discipline

For each scored wine, list the actual sources used. Separate:

- identity/origin sources
- origin-market price sources and any fallback benchmark sources
- quality/review sources

Do not mix unsupported claims into the score. If exact sources are missing, mark the candidate as incomplete.
