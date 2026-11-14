# Structural recipe-plan validation

M2, UI-02/UI-04; domain-level support for AC-01/AC-02 under ADR-0001/ADR-0003/ADR-0005. These pure rules support the [draft persistence slice](../architecture/recipe-draft-storage.md), without implementing a publication/start transition. D-03's versioned HTTP/JSON schemas and full publication requirements remain open. The draft unit/category catalogue is recorded below under proposed ADR-0009.

## Typed domain interface

`brewery_domain.recipe_plan.validate_plan(RecipePlan)` returns a tuple of `PlanIssue(code, path, message)` in deterministic collection order. Paths identify fields such as `additions[0].ingredient_id`. It does not mutate the input, save records, assign identifiers, convert units, or execute physical actions. Input collections use tuples and frozen dataclasses. Future adapters must parse and validate transport types before constructing these domain values.

| Value | Fields |
| --- | --- |
| RecipePlan | `version_id`, `ingredients`, `steps`, `additions` |
| Ingredient | `id`, `version_id`, optional `quantity`, `unit`, `name`, `category` |
| Step | `id`, `version_id`, `dependencies` (step IDs), optional `anchor_step_id`, `title`, `instructions` |
| Addition | `version_id`, `step_id`, `ingredient_id`, optional `quantity` and `unit` |

Identifiers are nonempty strings without surrounding whitespace, unique within each ingredient/step collection. They are internal identifiers, not a commitment to a database key type. Supply the complete plan for one version, including disconnected and parallel steps. References resolve only inside that supplied version; matching names never repair a missing reference. All child records must declare the selected version.

Dependencies and timing anchors form one directed graph. Self-references, missing steps, cross-version references, and cycles are rejected. Display order has no effect on reference identity or graph validity. A dependency and anchor to the same step are legal and count as one graph edge. Events, offsets, durations, confirmations, and schedule recalculation are later work.

Quantities, when present, must be finite positive Python `Decimal` values. Binary floats, booleans, zero, negative values, NaN, and infinity are rejected. Portion quantities are summed exactly across all steps using rational arithmetic; totals may be less than or equal to the planned ingredient amount. Addition units must equal the ingredient's unit whenever both are supplied. Supported draft tokens are `g`, `kg`, `oz`, `lb`, `mL`, `L`, `US_fl_oz`, `US_gal`, `count`, `packet`. Ingredient categories are `grain`, `hops`, `yeast`, `other`, or absent. Grain/hops require mass units when supplied. Unknown tokens/categories are rejected. No implicit conversion occurs.

Missing quantities/units remain `None`; they do not become zero. Totals cannot be fully checked while quantities or units are absent. An empty draft is structurally valid, and an empty issue tuple never implies publication readiness. Publication must separately require complete fields, recognized unit categories, ingredient specifications, and usable brewing steps. This validator does not enforce published-version immutability or historical batch snapshots (AC-03).

## Integration requirements and evidence

The PostgreSQL draft adapter runs validation on the complete proposed version within a transaction and saves no partial changes on failure. Real PostgreSQL tests now exercise version-scoped foreign keys, atomic replacement, and concurrent-edit behavior. HTTP/UI acceptance for AC-01/AC-02 remains pending; these rules and storage tests do not complete the end-to-end scenarios.

`tests/unit/test_recipe_plan.py` covers cross-version/missing references, dependency/anchor cycles, self-links, duplicate IDs, reorder/parallel behavior, incomplete drafts, invalid amounts, exact decimal boundaries under reduced precision, overallocated portions, unit mismatches, and 3,000-step graphs. Run `.venv/bin/python -m unittest tests.unit.test_recipe_plan -v` after installing the editable backend package.

## Manual ingredient entry

The M2/UI-04 ingredient API/editor builds on the existing schema and storage port. It reads a complete ordered ingredient list and replaces only that collection under the version's existing edit revision. It does not edit steps/additions or discard their references. The adapter validates the full resulting plan atomically: linked deletion, quantity underallocation, and unit incompatibility produce issues without partial saves. HTTP callers cannot set child version ownership. Existing metadata and non-ingredient plan records remain unchanged.

The [v1 ingredient contract](../../packages/communications/contracts/recipes/v1/README.md#ingredient-editing) bounds new writes, transports exact decimal strings, and preserves absent draft fields. The browser supports row addition/removal, names/categories/quantities/units, preserved unsaved edits, explicit conflict review, and phone/tablet/desktop interaction. Ingredient specifications, product catalogues, ordering controls, steps, publication, and extraction/conversion recommendations remain future slices. This provides additional HTTP coverage toward AC-01; it does not complete the full scenario or M2.

## Manual recipe step editing

The M2/UI-02 step API reads and atomically replaces the complete ordered step list under the same edit revision used by overview and ingredient writes. Stable IDs preserve dependency, anchor, and addition links when rows move. The adapter validates the complete resulting plan; cycles, missing references, and removal of a step that still owns an addition are rejected with no partial save. The editor allows incomplete titles/instructions, reordering with keyboard controls, and explicit dependency/anchor editing. Removal stays disabled while other steps depend on the step or it owns an addition. It does not add durations, offsets, vessel roles, targets, action types, confirmation requirements, publication, or timer behavior. This is a vertical slice toward AC-01/AC-02, not completion of UI-02 or M2.
