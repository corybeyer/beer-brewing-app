# Conversion proposal retention

C2b of the [conversion plan](../plan/extract-conversion.md), M2/UI-04/UI-05 and M6 reviewed adaptations, under [proposed ADR-0014](decisions/0014-conversion-proposal-retention.md). This persistence slice supports CV-08/CV-09/CV-12. It does not generate matches, apply a proposal to a draft, publish a recipe, or start a batch.

## Retained document and ownership

`0004_conversion_proposals` follows `0003_fermentable_catalogue` and adds `conversion_proposal`. Relational columns identify the proposal, owning recipe version, original edit revision, explicit creation time, and supported format. A foreign key retains recipe-version ownership. The bounded JSONB document is a closed historical representation of the [domain snapshot](../requirements/conversion-proposal-snapshots.md): full original/proposed recipes, complete selected catalogue profiles/component closure, exact C1 calculation inputs/results, and explanations. Live recipe and catalogue tables remain normalized and authoritative for new writes.

The codec in `brewery_database.proposal_document` explicitly registers supported dataclass types and requires their complete field sets. It encodes Decimal values as decimal strings, Fraction values as numerator/denominator strings, timestamps with their timezone, and ordered tuples as arrays. It performs no dynamic import or arbitrary class construction. Unknown types, unsupported versions, malformed values, excess nesting/size, NUL, and binary floating-point values are refused. The document limit is 4 MiB. SQL checks bind document headers to relational columns; domain validation enforces complete graphs, provenance, and calculation consistency on capture and load.

Historical documents intentionally contain copies rather than live catalogue foreign keys. A later product revision or recipe edit cannot change the meaning of an old proposal. Append checks that the selected immutable product revisions match authoritative catalogue records, while load remains independent of the current recipe/catalogue. Unknown original fields stay absent; the exact rational result remains separate from the explicit weighing quantity. Retention does not prove a manufacturer's claim, flavor equivalence, or mash feasibility.

## Transaction semantics

The pure `ConversionProposalStore` port exposes append/load. `PostgresConversionProposalStore` implements it in the database package. Append validates and encodes the proposal, holds a shared lock on its owning recipe-version row, reads the full current draft on that same connection, and compares it to the retained original and edit revision. Existing recipe writes take an exclusive lock on that row. A proposal cannot slip between a revision check and a concurrent recipe replacement: it is retained before that replacement, or it sees/rejects the changed original.

The adapter also verifies the copied catalogue revisions and inserts the immutable proposal within that transaction. A stale/missing original, inconsistent profile copy, invalid document, duplicate proposal ID, or database failure saves no proposal and does not change a recipe or catalogue. Separate proposals may refer to the same original revision. Reusing an existing ID is a conflict, not permission to overwrite. Retrying after a later recipe edit may report stale input before checking duplicate identity; callers can load an existing proposal explicitly.

Load returns the complete validated snapshot or None for a missing ID. It rechecks the document and relational headers; corrupted/unsupported retained data is unavailable, never a trusted conversion. Storage failures are sanitized at the port. Runtime grants are SELECT/INSERT only; UPDATE/DELETE/DDL and migration metadata writes remain denied. Direct privileged SQL is not a supported proposal editing workflow.

Retention closes the save-time race, not a future Apply-time race. Applying a retained proposal must again check the current revision and validate/remap the complete plan inside its own transaction. No Apply operation or user-facing control is introduced here.

## Migration and rollout

Upgrade adds the table without rewriting populated recipe/catalogue data. Empty downgrade takes an ACCESS EXCLUSIVE table lock before checking emptiness, then removes only the proposal table. Any retained proposal refuses downgrade and leaves both data and revision intact. Application rollback never downgrades the schema or restores over live data.

Source readiness/operator head advance together to `0004_conversion_proposals`. The deployment policy accepts reviewed forward transitions and same-revision adoption, rejects unknown/reverse revisions and mismatched application/operator pairs, and uses the prior API only when its declared schema matches the resulting database. Otherwise the retained health-only smoke service preserves access for recovery. Snapshot fingerprints include the proposal table, and verification restores its full document alongside recipes/catalogue in a disposable database.

Installed catalogue-only operations must be updated from the exact clean reviewed source commit after full CI and review, **before this schema release merges**. Follow the proposal-release section of the [rollout procedure](../../infrastructure/deployment/production/ROLLOUT.md). That administrator operation preserves credentials/configuration/state and does not itself migrate or restart the app. This development document is not evidence of a production operations update or proposal-schema adoption.

## Verification scope

Codec tests exercise exact round trips, malformed/unknown fields and numeric representations, complete immutable reconstruction, and resource limits. Real PostgreSQL tests exercise coherent append, stale/missing/same-revision-edited originals, authoritative product copies, concurrent recipe writers, duplicate inserts, rollback, historical reload after later edits, restricted grants, populated upgrades, empty/populated downgrade and its write race, plus populated snapshot backup/restore. Real container rollout/restore and ARM64 execution remain independent CI requirements. Final local results are recorded in the source-bound `.validation/pre-pr.json`; no absence of PostgreSQL coverage may be inferred away if the report lists a gap.
