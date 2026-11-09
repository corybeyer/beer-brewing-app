# ADR-0012: Sourced, immutable fermentable catalogue revisions

Status: Proposed — November 8, 2026

## Context

The C1 conversion core can size a specified replacement but has no product data. M2/UI-04 and the C2 stage of the extract-conversion plan need grain/DME/LME identity, sourced potential, known grain composition, color context, and flavor notes. Mutable catalogue rows would change later interpretations of an older proposal. Existing recipe rows must remain usable independently of a catalogue.

## Proposed decision

Add an append-only catalogue through a pure domain port and PostgreSQL migration `0003_fermentable_catalogue`. Product identities have a stable kind; revisions retain names/manufacturer, source label/URL/retrieval time, exact optional PPG and its provenance status/note, optional color range/unit/basis, flavor notes/tags, and optional complete grain composition. Yield and composition statuses distinguish manufacturer-reported data, manual assumptions, and unknown data. Unknown does not become zero or a default yield. A color number without its measurement/concentration basis is not sufficient catalogue data.

Store the product, revision, normalized flavor tags, and grain-component references in four tables. Known component shares describe the source grain bill by mass and total exactly one; components reference immutable grain revisions only. This makes nested-extract cycles impossible. The adapter appends one validated revision and its children atomically, rejects replacement/duplicate identities, and returns sanitized storage failures. Runtime grants permit SELECT/INSERT only; no catalogue UPDATE/DELETE or DDL. Normal application writes use the port; raw privileged SQL is not a supported editing workflow.

Do not attach products to existing recipe rows or store conversion proposals in this slice. Those writes need their own revision-checked snapshot/retention contract. Seed no assumed manufacturer catalogue and fetch no remote data at runtime. Curated/imported data must retain its source and assumptions; missing enzyme/feasibility data cannot establish mash readiness.

## Migration and release

Upgrade is additive to populated recipe schema `0002_recipe_drafts`. Empty catalogue downgrade locks all four tables before checking emptiness, removes only those tables, and retains recipe data. Any catalogue data refuses downgrade. Application readiness and operator heads advance together.

Extend the explicit production compatibility policy to the reviewed catalogue revision and forward transitions only. Preserve pre-migration exported-snapshot backups and schema-compatible rollback/retained-smoke fallback. Unknown revisions, reverse transitions, and mismatched operator/application pairs remain rejected. Add populated catalogue restore and real recipe-to-catalogue rollout coverage, including failed-candidate recovery. Review and install updated root operations from the exact clean reviewed commit before this schema release merges. No source change silently updates installed operations or downgrades live data.

## Alternatives and consequences

A mutable flat product list is simpler but loses historical meaning. A generic JSON blob obscures component ownership, source status, and color units. Creating proposal/batch tables now would settle future contracts prematurely. This slice therefore supplies only catalogue storage and its owning integrity rules. Product matching, ranked flavor variations, proposal retention/application, catalogue authoring UI, and full CV-05–CV-12 acceptance remain later work.

## References

- [Extract conversion plan](../../plan/extract-conversion.md)
- [Recipe storage](../recipe-draft-storage.md)
- [ADR-0005](0005-workspace-boundaries.md)
- [ADR-0010](0010-recipe-rollout-and-snapshot-backups.md)
