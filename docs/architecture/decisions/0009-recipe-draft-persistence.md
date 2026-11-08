# ADR-0009: Transactional recipe draft persistence

Status: Proposed — November 7, 2026

## Context

M2 needs the first recipe tables and a tested storage adapter (UI-02/UI-04/UI-05, AC-01/AC-02). The existing pure plan validator has no storage. D-03's publication, target, and classification contracts remain open. Production's installed deployer explicitly accepts only `0001_baseline`.

## Proposed decision

Add `0002_recipe_drafts` with recipe identities, numbered draft versions, version-local ingredients, ordered steps, dependency links, and ordered additions. Keep display names/instructions alongside structural values; absent draft fields stay NULL. Restrict status to draft until publication is separately implemented. Store exact decimal quantities and UTC timestamps. Use composite version-local keys/foreign keys for all plan links. Provide a domain storage protocol and a SQLAlchemy adapter with atomic create/load/replace operations, optimistic edit revisions, row locking, and validation of the complete proposed plan inside the transaction. Do not expose write APIs in this slice.

Use a small explicit unit catalogue for stored drafts: mass `g`, `kg`, `oz`, `lb`; volume `mL`, `L`, `US_fl_oz`, `US_gal`; counts `count`, `packet`. No conversion is implicit. Ingredient categories are `grain`, `hops`, `yeast`, `other`, or absent in incomplete drafts. Grain/hops require mass units when supplied; yeast/other can use the supported unit categories. Future HTTP contracts must validate publication completeness. No arbitrary JSON or unsupported target meanings are persisted.

Grant the application only table-specific draft privileges through the explicit migration operator. It cannot delete recipe identities/versions, run DDL, or edit migration metadata. Empty-schema downgrade locks all recipe tables before checking for data; populated recipe downgrade fails transactionally and requires a separately reviewed export/recovery plan. No automatic production downgrade is allowed.

## Compatibility and rollout

The first schema slice was intentionally blocked by the baseline-only production deployer. [Proposed ADR-0010](0010-recipe-rollout-and-snapshot-backups.md) now supplies a narrow forward-transition policy, root-installed operations updater, and consistent-snapshot backup implementation in source. Container/ARM64/rollout CI and an administrator operations update are required before merging/deploying the recipe schema. A candidate image or passing local tests cannot authorize that adoption. Existing production remains at its installed baseline. API readiness advances with the development migration head; old baseline applications cannot claim readiness against the new revision.

## Alternatives and consequences

Creating the full target ERD would settle unreviewed brewing semantics. An unversioned JSON draft blob would weaken relational integrity. Silent downgrade would destroy user work. This slice instead adds only draft plan ownership and atomic storage; it does not implement publication, batch snapshots, history, source/style/target editing, HTTP endpoints, or complete M2 acceptance. Real PostgreSQL tests must cover cross-version constraints, failed-save atomicity, conflicting writers, populated baseline upgrade, and downgrade refusal. CI container/ARM64 and production compatibility checks remain required before any merge.
