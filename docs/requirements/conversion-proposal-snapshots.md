# Conversion proposal domain snapshots

C2b, supporting M2/UI-04/UI-05 and M6 reviewed adaptations (AC-01/AC-02/AC-11/AC-13; evidence toward CV-08/CV-09/CV-11). [Proposed ADR-0013](../architecture/decisions/0013-conversion-proposal-snapshots.md) records the snapshot boundary. [Transactional retention and atomic Apply](../architecture/conversion-proposal-storage.md) implement this one-to-one slice under proposed ADR-0014; full CV-12 release verification remains separate.

## Values and capture

`brewery_domain.conversion_proposals` defines frozen `ConversionProposal` and `IngredientConversion` values. A proposal retains its identifier, explicit timezone-aware creation time, format `conversion-proposal/v1`, complete original `StoredDraft` including edit revision, complete proposed `RecipeDraft`, full selected catalogue revisions, and one to 100 explicit one-to-one substitution calculations. No timestamp, recovery, potential, or product match is invented.

Each calculation links one original ingredient to one proposed ingredient in the same position. It retains the exact C1 `ConversionResult`, target catalogue revision ID, optional source catalogue revision ID, explicit source/target potential-override explanations, and an optional weighing explanation. Manual sources without a product link require an override explanation. A selected product's absent or differing potential also requires one. C1 still requires explicit recovery, comparison point, and provenance on both sides. A catalogue PPG value is not equipment recovery.

`validate_proposal` returns deterministic `PlanIssue` values. `capture_proposal` raises `InvalidConversionProposal` on issues and otherwise returns the immutable value. Capture is a pure validation operation; it does not mean a proposal was saved. Snapshot collections, including nested recipe dependencies, must be tuples. Recipe quantities are finite positive Decimals with at most 24 digits and exponent -12 through 12 before portion arithmetic. Missing draft fields remain absent. This is a resource bound for this proposal format, not a claim that every existing draft is eligible for conversion.

Up to 200 full catalogue profiles can be retained. Every known extract component must resolve to a retained grain revision. Duplicate revision IDs, conflicting product kinds, and duplicate product/revision numbers are invalid. Existing catalogue validation still enforces provenance, exact bill totals, color context, and immutable typed children. No remote source is fetched. Full snapshots remain interpretable independently of future catalogue availability or product revisions; validation does not authenticate a manufacturer's claim.

## Calculation and recipe integrity

Recompute each result with the C1 domain calculator and compare its exact rational mass, gravity contribution, assumptions, and calculation version. A rounded decimal cannot replace the exact result. The source mass must equal the complete original ingredient quantity in its recorded unit. The proposed quantity uses the result unit. The picker displays a mass rounded to 0.001 of the chosen unit, retains the unrounded exact result and a scale-precision note, and requires a separate Apply action. This is display rounding, not a claim that every scale can measure that increment.

Recipe identity, version identity/number, name, description, step records, ingredient order, and unrelated ingredients/additions stay unchanged. Each changed ingredient needs evidence. Source ingredients must explicitly use grain/other categories; selected grain profiles require grain, DME/LME profiles require other. No hops/yeast conversion, inferred classification, blend generation, step adaptation, publication, or batch mutation is performed.

Preserve addition count, order, and step links; remap the ingredient link for the substitution. Known scheduled quantities need explicit original and proposed units. Preserve exact portion shares relative to planned/weighing quantities, or retain a weighing explanation for the adjustment. Complete proposed-plan validation still rejects overallocated quantities, cycles, wrong units, and broken/version-foreign links even when an explanation exists. An unknown portion quantity stays absent. An unknown portion unit stays absent; only an explicitly supplied unit is remapped to the target unit.

## Revision review and future storage

`require_current_proposal(proposal, current)` validates the proposal and compares the complete original draft and edit revision to a freshly loaded `StoredDraft`. Missing, different, or edited drafts raise `StaleConversionProposal`. Persistence repeats this check inside both append and Apply transactions. Apply also locks the recipe version, revalidates the proposed plan, replaces all plan rows, and advances one shared revision atomically; stale/replayed requests conflict without partial writes.

The `ConversionProposalStore` append/load/apply port has a PostgreSQL retention adapter and versioned local API. The UI lists sourced grain profiles, requires explicit potentials/recoveries/provenance/comparison point, shows exact and display-rounded results, and separates preview from Apply. A missing catalogue profile produces an empty state. See the [owning storage specification](../architecture/conversion-proposal-storage.md) and [HTTP contract](../../packages/communications/contracts/recipes/v1/README.md) for locking, migration/restore, and transport details.

C3 owns ranking and selected-blend sizing; those domain contracts do not generate persisted blend proposals. This C4 UI only offers one-to-one substitutions and does not implement ranking, optional flavor variations, blends, or mash-step adaptation. A valid snapshot does not establish flavor equivalence, mash feasibility, publication readiness, or any performed physical action.

## Verification

Domain tests exercise complete snapshots, exact recurring results, explicit assumptions, and portion remapping. Real PostgreSQL integration tests exercise append, revision-locked atomic Apply, whole-plan replacement, and stale/replayed conflicts. HTTP integration verifies empty/populated catalogue responses, preview creation, Apply, and replay rejection. Browser behavior and all CI/release checks remain separately verified.
