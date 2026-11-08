# Recipe draft storage

M2/UI-02/UI-04/UI-05; [proposed ADR-0009](decisions/0009-recipe-draft-persistence.md), [domain validation](../requirements/recipe-plan-validation.md), and AC-01/AC-02. This is a local development schema/adapter, with a local [v1 overview HTTP/editor slice](../../packages/communications/contracts/recipes/v1/README.md); that new UI/API capability is not deployed yet. Production adopted `0002_recipe_drafts` at `2df377693d647aa87ec0b98d5470d78fe93c379c` after the reviewed operations update, passing CI, and automatic rollout. See [actual host evidence](../plan/status.md#verified-production-recipe-schema-adoption) and [the rollout procedure](../../infrastructure/deployment/production/ROLLOUT.md#upgrading-installed-operations-before-the-recipe-release).

## Tables in `0002_recipe_drafts`

| Table | Identity and owned data |
| --- | --- |
| `recipe` | Nonempty text ID and UTC creation timestamp; stable identity across numbered versions |
| `recipe_version` | Globally unique text ID, owning recipe FK, positive version number unique within recipe, draft-only status, nullable name/description, positive edit revision, UTC created/updated timestamps |
| `recipe_ingredient` | Composite `(version_id, id)` PK, unique positive position per version, optional name/category/exact numeric quantity/unit |
| `recipe_step` | Composite `(version_id, id)` PK, unique positive position per version, optional title/instructions and version-local timing anchor |
| `recipe_step_dependency` | Version-local step/required-step FKs, unique link, positive per-step display position, no self-reference |
| `recipe_step_addition` | Positive position unique within version, version-local step/ingredient FKs, optional exact numeric quantity/unit |

Names/descriptions/instructions are text, not unvalidated JSON payloads. The initial slice does not include classification, sources, targets, ingredient specifications, timing events/durations, publication, batch execution, or snapshots. Do not infer those tables from the target ERD. Step anchors/dependencies/additions use composite foreign keys with the version included; identically named IDs in different versions cannot cross-link. Link constraints are deferred until transaction completion so complete plans can be inserted/replaced in any display order. Deletion never cascades through historical recipe/version identities.

NULL quantities/units are allowed in incomplete drafts. Supplied numeric quantities must be positive and finite, including when SQL bypasses the adapter. Recognized units are `g`, `kg`, `oz`, `lb`, `mL`, `L`, `US_fl_oz`, `US_gal`, `count`, `packet`; categories are `grain`, `hops`, `yeast`, `other`. Grain/hops require mass units when supplied. Other/yeast may use the supported unit categories. Unknown categories/units are rejected. The adapter requires addition units to match the ingredient unit without implicit conversion and checks exact portion totals. Full cycles, portion totals, and publication completeness are application-level rules, not SQL CHECK constraints.

## Port and transaction behavior

The store also lists bounded overview summaries in creation/ID order without loading every child record. `RecipeDraftService` coordinates idempotent creation and metadata-only updates. `brewery_domain.recipes` defines immutable `RecipeDraft(recipe_id, version_number, plan, name, description)` and `StoredDraft(draft, edit_revision)`, a `RecipeDraftStore` protocol, and domain exceptions. `PostgresRecipeDraftStore` in `brewery_database.recipes` implements:

- `create(draft)`: validate the complete proposed draft inside a transaction, insert a recipe identity if absent, and create the numbered version and all children atomically. Duplicate version ID or recipe/version number raises `DraftConflict`. Failed creates leave no orphan recipe identity.
- `load(version_id)`: return `StoredDraft` or `None`. Hold a shared lock on the version row while reading children, so a concurrent replacement cannot return mixed revisions.
- `save(draft, expected_revision)`: lock the version row, reject stale revisions/identity changes/non-draft state, validate the whole plan, replace children, and increment the edit revision in one transaction. The recipe ID/version number cannot be changed. Missing versions raise `DraftNotFound`; stale edits raise `DraftConflict`; invalid plan/metadata raises `InvalidDraft` with field-specific issues. A database failure rolls the whole replacement back and crosses the port as RecipeStorageUnavailable with no driver details.

Tuple order determines ingredient/step/addition positions; dependency order is preserved within each step. Repeated dependency IDs are normalized to one link, preserving first occurrence and any independent timing anchor. Amounts remain `Decimal`, with exact rational totals during validation. Runtime SQL descriptions never create tables; historical DDL is frozen in the migration.

The explicit migration operator passes the selected application role to Alembic. The owning migration grants SELECT/INSERT on recipe identities, SELECT/INSERT/UPDATE on versions, and SELECT/INSERT/UPDATE/DELETE on draft children. It grants no DDL, version/recipe deletion, or metadata writes. Plain low-level Alembic commands do not select or repair application-role grants; use the explicit operator after provisioning.

## Upgrade, compatibility, and rollback

`0002_recipe_drafts` is additive from `0001_baseline`; existing unrelated populated tables remain untouched. Development readiness expects exactly `0002_recipe_drafts`. The old baseline-only API will report unavailable at the new revision, so image rollback compatibility must be reviewed explicitly. No automatic schema downgrade is safe.

Downgrade first acquires ACCESS EXCLUSIVE locks on every recipe table, then checks emptiness inside the migration transaction. Any recipe data makes it fail without changing tables or revision. Empty downgrade removes only the six new tables and restores baseline revision tracking. A populated downgrade needs a separate reviewed export/recovery procedure; it is not provided as an overwrite-live command.

The Pi deployer was updated from the reviewed PR commit before the recipe schema merged. The source policy under [proposed ADR-0010](decisions/0010-recipe-rollout-and-snapshot-backups.md) now permits only matching baseline/recipe application/operator pairs and reviewed forward transitions. It restores an old API only when the resulting schema matches; otherwise it restores the retained smoke service with all data preserved. Exported-snapshot verification supports concurrent writes. The expanded rollout CI passed, the administrator installed reviewed operations, and automatic production migration succeeded. Future revisions still require a new reviewed compatibility policy; do not infer support for unknown migrations.

## Verification

Real PostgreSQL tests in `tests/integration/test_recipe_drafts.py` exercise draft round trips, exact amounts, NULL preservation, replacement/reordering, failed-create/save atomicity, SQL foreign-key/check constraints, unknown references/cycles, edit conflicts with overlapping connections, coherent concurrent reads, populated baseline upgrade, downgrade refusal, and an in-flight create racing downgrade. `tests/integration/test_database_roles.py` checks actual authenticated runtime privileges. These validate storage-level support for AC-01/AC-02; HTTP/UI acceptance and AC-03 remain pending. PostgreSQL 17 integration and the source-bound pre-PR command are required; container/ARM64/rollout validation remains separate.
