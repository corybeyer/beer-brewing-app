# Conversion proposal domain snapshots

C2b first slice, supporting M2/UI-04/UI-05 and M6 reviewed adaptations (AC-01/AC-02/AC-13; domain evidence toward CV-08/CV-09). [Proposed ADR-0013](../architecture/decisions/0013-conversion-proposal-snapshots.md) records the boundary. Durable retention, transactional concurrency, and CV-12 proposal-schema verification remain future work.

## Values and capture

`brewery_domain.conversion_proposals` defines frozen `ConversionProposal` and `IngredientConversion` values. A proposal retains its identifier, explicit timezone-aware creation time, format `conversion-proposal/v1`, complete original `StoredDraft` including edit revision, complete proposed `RecipeDraft`, full selected catalogue revisions, and one to 100 explicit one-to-one substitution calculations. No timestamp, recovery, potential, or product match is invented.

Each calculation links one original ingredient to one proposed ingredient in the same position. It retains the exact C1 `ConversionResult`, target catalogue revision ID, optional source catalogue revision ID, explicit source/target potential-override explanations, and an optional weighing explanation. Manual sources without a product link require an override explanation. A selected product's absent or differing potential also requires one. C1 still requires explicit recovery, comparison point, and provenance on both sides. A catalogue PPG value is not equipment recovery.

`validate_proposal` returns deterministic `PlanIssue` values. `capture_proposal` raises `InvalidConversionProposal` on issues and otherwise returns the immutable value. Capture is a pure validation operation; it does not mean a proposal was saved. Snapshot collections, including nested recipe dependencies, must be tuples. Recipe quantities are finite positive Decimals with at most 24 digits and exponent -12 through 12 before portion arithmetic. Missing draft fields remain absent. This is a resource bound for this proposal format, not a claim that every existing draft is eligible for conversion.

Up to 200 full catalogue profiles can be retained. Every known extract component must resolve to a retained grain revision. Duplicate revision IDs, conflicting product kinds, and duplicate product/revision numbers are invalid. Existing catalogue validation still enforces provenance, exact bill totals, color context, and immutable typed children. No remote source is fetched. Full snapshots remain interpretable independently of future catalogue availability or product revisions; validation does not authenticate a manufacturer's claim.

## Calculation and recipe integrity

Recompute each result with the C1 domain calculator and compare its exact rational mass, gravity contribution, assumptions, and calculation version. A rounded decimal cannot replace the exact result. The source mass must equal the complete original ingredient quantity in its recorded unit. The proposed quantity uses the result unit. A different weighing quantity requires a nonblank explanation, retained alongside the unrounded result. This allows explicit reviewed rounding/adjustments; it does not automatically recommend them.

Recipe identity, version identity/number, name, description, step records, ingredient order, and unrelated ingredients/additions stay unchanged. Each changed ingredient needs evidence. Source ingredients must explicitly use grain/other categories; selected grain profiles require grain, DME/LME profiles require other. No hops/yeast conversion, inferred classification, blend generation, step adaptation, publication, or batch mutation is performed.

Preserve addition count, order, and step links; remap the ingredient link for the substitution. Known scheduled quantities need explicit original and proposed units. Preserve exact portion shares relative to planned/weighing quantities, or retain a weighing explanation for the adjustment. Complete proposed-plan validation still rejects overallocated quantities, cycles, wrong units, and broken/version-foreign links even when an explanation exists. An unknown portion quantity stays absent. An unknown portion unit stays absent; only an explicitly supplied unit is remapped to the target unit.

## Revision review and future storage

`require_current_proposal(proposal, current)` validates the proposal and compares the complete original draft and edit revision to a freshly loaded `StoredDraft`. Missing, different, or edited drafts raise `StaleConversionProposal`. This is a review-time check. A change after the check remains possible; a future retention/apply adapter must repeat the check inside its transaction and save nothing on conflict. The pure helper supplies no concurrent-write or durable-restart guarantee.

The next C2b slice owns schema, append/load retention, restricted grants, migration/restore evidence, and deployment compatibility. C3/C4 own matching, blend/ranking generation, mash/boil/hop review, versioned API errors, picker/preview, explicit Apply, and transactionally safe recipe changes. This first format is intentionally limited to C1 one-to-one substitutions; extend/version it explicitly for blends or step adaptation. A valid snapshot does not establish flavor equivalence, mash feasibility, publication readiness, or any performed physical action.

## Verification

`tests/unit/test_conversion_proposals.py` exercises complete immutable snapshots, retained exact recurring results, low Decimal precision, stale/wrong/same-revision-edited drafts, altered arithmetic/version evidence, missing/overridden product yields, full extract-component closure, independent future catalogue changes, explicit weighing adjustments, unchanged metadata/steps/unrelated ingredients, reordered/missing/rerouted additions, unknown quantity/unit preservation, conflicting product identities, duplicate conversion evidence, mutable nested inputs, and resource-bounded quantities. No database/API/browser behavior is implemented by this slice.
