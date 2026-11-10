# Grain matching and selected-blend sizing

First C3 domain slice, supporting M2/UI-04/UI-05 and M6 reviewed adaptation; numerical/evidence checks toward CV-05/CV-06/CV-07/CV-10. [Proposed ADR-0015](../architecture/decisions/0015-grain-match-ranking.md) records the choice. Pure ranking and blend math do not complete C3 or picker/apply acceptance.

## Inputs and immutable evidence

`brewery_domain.fermentable_matching.rank_grain_matches(source, grains, include_variations=False)` accepts one complete DME/LME `CatalogRevision`, up to 1,000 grain revisions in a tuple, and an explicit boolean variation choice. Existing catalogue provenance, numeric bounds, color context, tags, and complete-bill rules are validated before ranking. Missing/invalid profile data is never silently repaired. `MatchingInputError.path` identifies invalid input. Reject non-extract sources, non-grain candidates, duplicate revision IDs/product revision numbers, and conflicting stable product kinds. The supplied set is explicit; no database read, remote fetch, manufacturer seed, or newest-revision selection occurs.

The frozen `GrainMatches` result retains the complete source, ordered options, review reasons, and ranking version `grain-ranking/v1`. A frozen `GrainMatch` retains its relation, complete grain revisions and exact Decimal mass fractions, shared flavor tags, exact rational descriptor similarity/color gap when available, and review reasons. Input iteration order never breaks ties. Later immutable catalogue revisions do not reinterpret an existing result.

## Closest composition first

When every component of the source's complete grain bill resolves to a supplied grain revision, that retained bill is first. `manufacturer_composition` means the source reports the bill with manufacturer attribution; it is not independent laboratory verification. `assumed_composition` retains the explicit manual assumption and explanation. Both preserve the source's component shares/order and all original revisions.

An unknown bill produces no composition-match option. A known/assumed bill with missing component revisions also produces no composition option and reports each missing grain. Do not substitute a partial bill or infer missing shares. The function still permits separately labeled variations when explicitly requested. It never claims that a dark extract's color reveals its grain bill.

## Optional variations and deterministic order

Single-grain variations each have mass fraction one. Do not duplicate the sole grain from a complete single-grain composition as another option. The algorithm does not enumerate invented blends.

For supplied source/candidate tags, descriptor similarity is exact Jaccard intersection/union. Retain sorted shared tags and full original descriptors; these are source-reported descriptors, not measured finished-beer flavor scores. If either tag set is absent, the score is absent. Empty tags never become a perfect match.

Color is comparable only if source and candidate declare exactly the same unit and measurement basis. The gap is zero for overlapping ranges, otherwise the exact distance between the closest endpoints. Convert endpoints to Fractions before arithmetic, avoiding midpoints and Decimal-context rounding. Different units/bases remain incomparable, including extract concentration versus dry grain. No Lovibond/SRM/EBC conversion, finished-beer color calculation, or flavor-equivalence claim occurs.

Candidates with either positive descriptor overlap or comparable color evidence receive relation `variation`. Those with neither are `unranked_variation` and report `no_similarity_evidence`; they are available for explicit review, not meaningful ranked recommendations. Sort usable variations first; within that group sort available descriptor similarity before absent similarity, descending similarity, available comparable color before absent color, ascending color gap, and finally revision ID. Unranked variations have no positive similarity signal or comparable color and sort by their retained zero/absent evidence and stable ID. The complete composition always precedes either variation group.

## Missing data and review

`MatchReview` keeps a controlled reason code and optional associated revision ID. Missing source/grain potential stays absent; `source_potential_required` / `grain_potential_required` prevent a yield assumption from becoming a hidden default. Manual potentials remain explicitly assumed. Missing descriptors, color, incompatible color basis/unit, unresolved composition, an empty supplied grain set, and assumed composition are separately reported. No quantity is calculated by ranking.

Every ranking result reports `recovery_required`, `mash_feasibility_review`, and `whole_recipe_review`. The latter includes mash/boil/hop-balance review before adaptation. A complete bill or matching descriptors do not prove enzyme sufficiency, fermentability, extract/grain process equivalence, readiness, or identical beer. Versioned proposal/API integration and explicit C4 preview/apply remain future capabilities. No recipe, step, addition, publication, batch, or equipment action is changed by ranking or sizing.

## Exact sizing of a selected blend

`brewery_domain.blend_conversion.convert_grain_blend(source_mass, source_yield, targets, target_unit)` is separate from ranking. It accepts C1 `Mass`/`FermentableYield` source inputs, a tuple of one to 100 frozen `BlendTarget` values, and a mass unit. Each target retains the full grain profile, an exact Decimal mass fraction, explicit `FermentableYield`, and optional potential-override note. A caller can turn each `MatchedGrain` into a `BlendTarget` by supplying its declared yield/recovery/reference-point assumptions. Ranking does not supply those assumptions.

Shares describe grain mass, not gravity contribution, and must total exactly one. Reject duplicates, conflicting product/revision identities, non-grain/invalid profiles, non-finite/untyped/nonpositive or excessive shares, incompatible comparison points, missing or invalid recovery, and unsupported units. Missing or differing catalogue PPG requires a nonblank explicit override explanation. Notes are bounded to 4,000 characters and reject NUL. C1 numeric/resource bounds still apply; shares permit at most 24 digits and exponent -12 through 12, with value above zero and at most one. No hidden source/target recovery or yield default is used.

The calculation reuses public C1 conversions to obtain source gravity contribution and each grain's contribution per requested mass unit. Compute the exact mass-weighted contribution, divide source contribution by that value, then multiply total mass by each exact share. The frozen `BlendConversionResult` retains complete source and target assumptions, unrounded rational total/component masses, each component's gravity contribution, common mass unit, total gravity contribution, and calculation version `grain-blend-gravity/v1`. Component masses sum to total mass; contributions sum to the conserved source contribution. Different recoveries may make component gravity shares differ from their mass shares. Display/weighing rounding is outside this pure result.

The numerical result establishes gravity contribution at the same declared comparison point, not flavor, color, fermentability, enzyme sufficiency, a suitable process, or recipe readiness. It does not inspect or remap recipe ingredients/additions. The current C2b snapshot format retains one-to-one C1 results; blend proposal retention and application need a deliberate later format/integration extension. Blend arithmetic alone does not complete CV-07's linked recipe preservation requirements.

## Verification

`tests/unit/test_fermentable_matching.py` covers reported versus assumed composition, complete bill retention, unknown dark extract, unresolved components, optional/unranked variations, exact descriptor/color evidence under low Decimal precision, incompatible units/bases, deterministic ordering/ties, missing yields/recovery review, full immutable source/profile retention, single-grain deduplication, invalid/mutable inputs, conflicting identities, and input size bounds. Synthetic profiles are not manufacturer recommendations or production seed data.

`tests/unit/test_blend_conversion.py` covers agreement with C1 for a single grain, differing component yields/recoveries, exact mass/contribution totals, equivalent mass units, explicit fermenter assumptions, low Decimal precision, incomplete shares, missing/overridden potentials, duplicate/conflicting identities, source/target provenance, resource limits, and a 100-component blend. Focused matching/sizing checks total 36 tests. Full pre-PR results remain source-bound in `.validation/pre-pr.json`; independent CI remains required.
