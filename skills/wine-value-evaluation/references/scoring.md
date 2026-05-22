# Wine value scoring rubric

Use this rubric when the user asks for a ranked value list and has not provided custom weights.

## Required fields per wine

- `buyer_market_price`: normalized to one standard bottle, usually 750 ml, after local discounts and required fees when known.
- `origin_market_median_price`: median of comparable prices in the wine’s country-of-origin market, same vintage and bottle size when possible.
- `price_gap_pct`: `(buyer_market_price / origin_market_median_price - 1) * 100`.
- `benchmark_market`: country-of-origin by default; if a fallback is used, name it explicitly and lower confidence.
- `quality_sources`: provider ratings/reviews with exact-match confidence.
- `identity_confidence`: exact / strong / moderate / weak / reject.
- `origin_status`: confirmed / likely / ambiguous / reject.

## Price-gap score, 0-100

The score rewards low buyer-market premium versus the origin-market median.

| Buyer-market price vs origin-market median | Price-gap score |
| --- | ---: |
| <= origin-market median | 100 |
| +0% to +20% | 90-100 |
| +20% to +40% | 75-90 |
| +40% to +70% | 50-75 |
| +70% to +100% | 25-50 |
| > +100% | 0-25 |

Use interpolation inside bands. If shipping/pickup fees are unknown, compute with known price and mark confidence lower. If origin-market prices are unavailable and a secondary benchmark is used, keep the same formula but add a `fallback_benchmark` confidence flag.

## Quality score, 0-100

Normalize ratings conservatively:

- 100-point critic scores: use directly.
- 20-point scores: multiply by 5.
- 5-star community scores: multiply by 20, but cap confidence when rating count is low.
- Guide stars/awards without numeric score: convert only as a coarse signal and explain the mapping.
- Text-only reviews: use as qualitative evidence, not a numeric score, unless the user accepts a subjective conversion.

Default provider weighting:

| Source type | Weight guidance |
| --- | ---: |
| Named critic / specialist publication, exact vintage | 1.20 |
| Expert guide or magazine, exact vintage | 1.10 |
| Wine-Searcher aggregate / merchant average, exact wine | 1.00 |
| CellarTracker with meaningful review count | 1.00 |
| Vivino with large rating count | 0.90 |
| Retailer customer reviews | 0.60-0.80 |
| Producer/importer claims | identity evidence only; not quality score |

If fewer than 3 quality providers are available, still score the wine but add a visible `quality_evidence_limited` flag.

## Final score

Default:

`final_score = 0.50 * price_gap_score + 0.50 * quality_score`

Recommended variants:

- Gift value: 45% price, 45% quality, 10% recognizability/style fit.
- Pure bargain hunting: 65% price, 35% quality.
- Special bottle: 30% price, 70% quality.

Only use variants when the user asks or the context clearly implies them. Always disclose weights.

## Confidence flags

Do not hide uncertainty in the final score. Add flags next to each candidate:

- `exact_match`: producer, cuvée, vintage, and size match across buyer-market, origin-market, and quality sources.
- `vintage_mismatch`: same wine but different vintage used for price or quality evidence.
- `low_review_count`: community score exists but has too few ratings to rely on.
- `marketplace_name_ambiguous`: local listing name is shortened/translated and exact cuvée remains uncertain.
- `origin_unverified`: region/appellation not confirmed through producer/importer/authoritative source.
- `price_evidence_limited`: fewer than 3 usable origin-market prices.
- `fallback_benchmark`: the comparison market is not the wine’s country-of-origin market.
- `quality_evidence_limited`: fewer than 3 usable quality sources.
- `availability_unverified`: app/login/store/age gate may change purchase feasibility.

Candidates with `origin_status = reject` or `identity_confidence = reject` should not be ranked as valid options.
