# Extract conversion and brewing calculator plan

Status: proposed implementation plan, November 8, 2026. The brewer agreed to the interaction direction below; catalogue choices, schema design, and later delivery stages remain proposed. Supports M2/UI-04/UI-05 ingredient planning and M6 reviewed adaptations/AC-13. It does not complete those milestones or authorize physical brewing actions.

## Brewer experience

Select an ingredient's dry malt extract (DME) or liquid malt extract (LME) product, original mass, and unit. Show the **closest match first**, with an expandable **Explore flavor variations** group in the same picker. Each choice shows the proposed grain bill and amounts, expected color/flavor contributions, differences from the closest match, and the basis for its match. Prefer known manufacturer composition; clearly identify inferred blends. Do not invent a numeric confidence score from flavor tags.

Selection opens a preview comparing original and proposed ingredients and showing yield, efficiency, units, sources, and assumptions. Only **Apply to draft** saves a reviewed proposal. Preserve the original recipe/extract entries, attribution, original units, product/catalogue revision, calculation version, and any user overrides. A flavor variation is labeled as a deliberate recipe change, rather than an equivalent product. Missing product data remains missing; it never becomes a precise recommendation.

Start with unhopped malt extracts. Hopped extracts, unknown mixed fermentables, and unknown blend composition require manual review. Existing specialty grains must remain distinct from specialty malts already present in an extract. Retain stable links to steps/additions or require an explicit remapping review. Replacing extract with grain also requires reviewing mash instructions; a matching gravity estimate never establishes that a recipe is ready to brew.

## Sources and what each establishes

Reviewed November 8, 2026. These links are calculation/design references, not runtime dependencies or permission to copy a site's software, catalogue, or prose. Recheck source/manufacturer data when importing a catalogue revision; preserve the data used by existing proposals.

| Source | Calculation or planning use | Limits |
| --- | --- | --- |
| [Brewer's Friend: extract/base grain](https://www.brewersfriend.com/extract-to-base-grain-conversion-calculator/) | Explicit source/target potential and recovery equation; selectable mass units | Capture the chosen efficiency and comparison point, rather than copying defaults invisibly |
| [Brewer's Friend: LME/DME](https://www.brewersfriend.com/lme-dme-conversion-calculator/) | Published liquid/dry example uses LME 37 PPG and DME 45 PPG | Those are this calculator's assumptions, not every product's specification |
| [Complete Calculators: extract/all-grain](https://completecalculators.com/calculators/homebrewing/extract-to-all-grain-conversion-calculator) | Documents approximate LME 36, DME 44, grain 36 PPG | Its different assumptions should produce different answers; do not average calculator outputs |
| [Jay's conversion chart](https://jaysbrewingblog.com/2011/11/17/lazy-chart-for-converting-dme-lme-grain/) | Quick comparison: one mass unit of grain corresponds to 0.75 LME or 0.60 DME | Fixed ratios omit an adjustable efficiency; only compare under compatible assumptions |
| [AHA: three-step conversion guide](https://homebrewersassociation.org/how-to-brew/3-simple-steps-converting-grain-recipes-extract/) | Efficiency-dependent conversion table, base-malt identification, and specialty-grain handling | Rounded table entries are not universal product yields |
| [AHA: working with extract recipes](https://homebrewersassociation.org/how-to-brew/working-with-extract-recipes/) | Matching source blends and recipe parameters; reviewing color, flavor, and boil differences | Matching gravity alone does not establish identical beer |
| [Malt substitution guide](https://yeasthopshaven.com/brewing-ingredients/malt-substitution-guide-for-homebrew/) | Candidate substitution ideas to investigate | Broad color-based substitutions and fixed ratios need manufacturer checks; not an automatic equivalence catalogue |
| [Foambyte: calculator collection](https://foambyte.com/calculators/) | Calculator organization and candidate tools | Implement shared local domain rules; no remote calculator calls from the Pi |
| [Foambyte: grain/extract](https://foambyte.com/calculators/grain-to-extract-conversion/) | Same yield/recovery equation; examples use grain 36, DME 42, LME 36 PPG | Its DME assumption differs from the other references |
| [Foambyte: efficiency](https://foambyte.com/calculators/brewhouse-efficiency-calculator/) | Distinguishes kettle/pre-boil mash efficiency from fermenter brewhouse efficiency | Do not interchange the two measurement points |
| [Briess: extract products](https://brewingwithbriess.com/products/extracts/) | Manufacturer composition and sensory information for matching known products | Product-specific; preserve source/version instead of generalizing a brand to every extract |
| [Briess: Dark Munich example](https://www.brewingwithbriess.com/wp-content/uploads/documents/Briess-PISB-Dark-Munich-Malt-30L.pdf) | Example of sourced malt/toast descriptors and usage-dependent character | Ingredient sensory notes are contributions, not a guarantee of finished-beer flavor |
| [NIST Handbook 44, Appendix C](https://www.nist.gov/document/2026-nist-handbook-44-appendix-c) | Avoirdupois mass conversion: 1 lb = 0.45359237 kg and 16 oz = 1 lb | Ounces here are mass, not fluid ounces |

## Calculation contract

The [Brewer's Friend equation](https://www.brewersfriend.com/extract-to-base-grain-conversion-calculator/) and [Foambyte derivation](https://foambyte.com/calculators/grain-to-extract-conversion/) conserve estimated gravity contribution. In compatible units:

```text
Q = source_mass × source_potential × source_recovery
replacement_mass = Q / (replacement_potential × replacement_recovery)
```

Here recovery is a fraction in (0, 1], so an entered 75% becomes exactly 0.75. Potential is gravity points × US gallons per pound (PPG); it is not specific gravity such as 1.037. Q has units of gravity points × US gallons when source mass is in pounds. Both potentials must have the same basis. The core normalizes g/kg/oz/lb explicitly; it does not accept fluid volume as ingredient mass. Recipe volume is unchanged in this first conversion: matching Q only matches estimated gravity at the same wort volume. Scaling/dilution is a separate calculation.

Recoveries must refer to the same comparison point on both sides. For a kettle comparison, grain uses mash/lauter recovery and a fully dissolved extract uses 1. For a fermenter comparison, both sides must explicitly account for their retention through downstream losses. Do not combine grain brewhouse recovery with an implicit extract kettle recovery. Some calculators conventionally use extract recovery 1 with a grain “brewhouse” percentage; reproduce that only as an explicit benchmark assumption, not as a hidden equipment setting. The [AHA guide](https://homebrewersassociation.org/how-to-brew/3-simple-steps-converting-grain-recipes-extract/) uses mash efficiency; [Foambyte](https://foambyte.com/calculators/brewhouse-efficiency-calculator/) explains the distinct measurement points.

Require supplied yield/recovery values and provenance. Prefer verified product-specific potential; label generic assumptions and user overrides. Manufacturer laboratory extract percentages cannot be treated directly as PPG without resolving their units and moisture/analysis basis. That import rule needs a separate sourced specification.

Use exact arithmetic internally and round only for display or an explicit weighing proposal. Do not round an intermediate quantity and use that rounded value for the inverse conversion. Gravity contribution does not establish fermentability, final gravity, ABV, color, enzyme sufficiency, or flavor equivalence.

### Worked examples and benchmark fixtures

The examples below apply the cited formulas; their arithmetic is calculated here. Each fixture carries its own assumptions. Example masses are illustrative and are not a recommended recipe.

| Fixture | Inputs | Expected result before display rounding |
| --- | --- | --- |
| CF-01: liquid to dry | 3 lb LME at 37 PPG, DME at 45 PPG, both recovery 1 at the same point ([Brewer's Friend](https://www.brewersfriend.com/lme-dme-conversion-calculator/)) | 3 × 37 / 45 = 37/15 lb, about 2.466667 lb DME |
| CF-02: dry to grain | 3 lb DME at 45 PPG/recovery 1; grain at 37 PPG/recovery 0.75, kettle basis; explicit illustrative inputs using the general equation | 135 / 27.75 = 180/37 lb, about 4.864865 lb grain |
| CF-03: grain to dry | 5 kg grain at 36 PPG/recovery 0.75; DME 42 PPG/recovery 1; matching the [Foambyte example](https://foambyte.com/calculators/grain-to-extract-conversion/) convention | 5 × 36 × 0.75 / 42 = 45/14 kg, about 3.214286 kg DME |
| CF-04: grain to liquid | Same grain inputs; LME 36 PPG/recovery 1 ([Foambyte](https://foambyte.com/calculators/grain-to-extract-conversion/)) | 3.75 kg LME |
| CF-05: chart compatibility | 10 lb grain, assumed 36 PPG/recovery 0.75; LME 36 and DME 45 PPG/recovery 1 | 7.5 lb LME or 6 lb DME, reproducing [Jay's chart](https://jaysbrewingblog.com/2011/11/17/lazy-chart-for-converting-dme-lme-grain/). The yield/recovery values are our compatible assumptions, not values stated by Jay |

For a later selected blend with mass shares w_i totaling exactly 1, use `weighted_yield = sum(w_i × P_i × E_i)`, then `total_grain_mass = Q / weighted_yield` and `grain_i_mass = total_grain_mass × w_i`. This algebra extends the same conservation equation; it is our proposed blend calculation, not a formula supplied by a flavor-matching site. Gravity math sizes a chosen blend; it cannot discover an unknown extract's composition.

## Delivery slices

| Slice | Reviewable outcome | Dependencies/limits |
| --- | --- | --- |
| C1: pure math | Typed, immutable inputs; explicit yields, recoveries, reference point, mass units, provenance; exact conversion and reference tests | Existing domain boundary; no default catalogue, schema, HTTP endpoint, or recommendation UI |
| C2a: product catalogue data | [Immutable sourced profiles](../architecture/fermentable-catalogue.md) for grain/DME/LME, exact known grain bills, color/flavor notes, and revisions | Local schema/adapter implemented; require complete checks, reviewed root-operations update, rollout/restore CI, and actual adoption |
| C2b: proposal snapshots | Retain original/proposed recipe inputs, selected product revisions, sources, overrides, and calculation/efficiency assumptions | First pure [domain snapshot contract](../requirements/conversion-proposal-snapshots.md) in development; transactional storage and revision-checked retention remain next |
| C3: proposal service | Generate closest-match proposal, then separately labeled variations; calculate selected blend amounts; explain missing/uncertain data | First pure [grain-ranking and selected-blend sizing contract](../requirements/fermentable-matching.md) in development; proposal/API integration and feasibility/diastatic review remain owning slices |
| C4: picker/apply | Grouped choices, comparison preview, explicit Apply to draft, immutable original and assumption snapshot | Atomic revision-checked application; preserve/remap step links; handle concurrent changes; no publication/start implied |
| C5: calculator page | Conversion and efficiency tools reuse the same domain rules as recipes | Versioned API; no duplicate browser math or external runtime dependency |
| Later calculator slices | Strike-water temperature, cooler mash-tun calibration, boil-off and gravity adjustment; then color/bitterness and other tools | Separate sourced models, units/measurement purposes, tests, and review. [Foambyte's collection](https://foambyte.com/calculators/) is a navigation/model reference, not evidence that all these functions are implemented |

Recipe step editing and publication remain M2 work; this conversion foundation does not replace them. Catalogue-driven proposals need a separate schema change even though manual ingredients already have tables. All acceptance work uses disposable records; none creates test recipes in production.

## Acceptance and failure checks

These are conversion-plan IDs, separate from the repository's AC-01–AC-14. Passing C1 tests establishes only the numerical subset.

| ID | Required evidence |
| --- | --- |
| CV-01 | Reproduce CF-01–CF-05 under explicit per-fixture assumptions; calculator differences remain visible |
| CV-02 | Exact inverse round trips and equivalent g/kg/oz/lb inputs conserve Q; lower target grain recovery needs more grain |
| CV-03 | Reject missing, non-decimal, non-finite, zero/negative amounts/yields, recovery outside (0,1], unknown units/reference points, or mismatched comparison points; no fabricated output |
| CV-04 | Keep results deterministic under changed caller decimal precision; validate numeric size bounds before rational conversion; display rounding does not change stored originals |
| CV-05 | Known product blends rank before inferred alternatives; unknown dark extract never becomes a claimed exact grain bill; flavor variations remain explicitly labeled |
| CV-06 | Missing efficiency, product yield, or measurement basis requires input/review; assumed and measured values remain distinct |
| CV-07 | Preserve specialty grains and avoid double-counting extract components; validate selected blend shares and every existing addition link |
| CV-08 | Preview/apply retains original recipe, product/catalogue/calculation versions, sources, overrides, and comparison-point assumptions; published/batch history stays unchanged |
| CV-09 | Concurrent edits reject stale proposal application without partial changes; browser failures retain the reviewed proposal |
| CV-10 | Whole-recipe adaptation flags mash/boil/hop-balance review; no promise of identical flavor, readiness, or performed physical actions |
| CV-11 | Phone/tablet/desktop, keyboard, accessible labels, explicit empty/loading/failure states; standalone tool and recipe proposal agree for identical inputs |
| CV-12 | New catalogue/proposal schema survives migration, restricted-role use, and verified restore under deployment compatibility checks before release |


## C1 domain interface and current evidence

`brewery_domain.extract_conversion.convert_fermentable(Mass, source_yield, target_yield, target_unit)` is the first implemented slice. Frozen `FermentableYield` values require Decimal `potential_ppg`, Decimal `recovery_fraction`, a comparison point (`kettle` or `fermenter`), and nonblank provenance. No product yield or recovery defaults are supplied. The core does not infer grain/DME/LME identity; later catalogue adapters must validate ingredient-specific assumptions.

Mass accepts positive finite Decimal input, or a positive Fraction for chaining an exact computed result. Decimal inputs allow at most 24 digits, exponents -12 through 12, and magnitude below 10^13; rational mass inputs allow numerator/denominator up to 512 bits. These are numerical resource bounds, not assertions that all inputs within them are realistic brewing values. Floats, integers, booleans, numeric strings, absent values, unknown/fluid mass units, invalid recoveries, and mismatched comparison points fail with `ConversionInputError.path` before a result is returned. Future transport adapters must parse bounded decimal strings and preserve the comparison-point/provenance information.

The result retains source mass and both yield assumptions, target mass as an exact Fraction with its requested unit, gravity contribution in points × US gallons, and calculation version `gravity-equivalence/v1`. It does not mutate a recipe, round a weighing proposal, call a calculator site, or provide a flavor/readiness recommendation. The first C3 slice now separately implements exact selected-blend sizing under `grain-blend-gravity/v1`; proposal/API integration remains future work.

Sixteen focused tests passed with `.venv/bin/python -m unittest tests.unit.test_extract_conversion -v`, covering CF-01–CF-05, differing defaults, exact public-interface inverse conversions, mass-unit equivalence, recovery sensitivity, changed Decimal context, provenance/immutability, and invalid/bounded inputs (numerical coverage toward CV-01–CV-04). Final full pre-PR results remain source-bound in `.validation/pre-pr.json`; CI is required independently. This is not evidence for catalogue, proposal, UI, or full M2/M6 acceptance.
