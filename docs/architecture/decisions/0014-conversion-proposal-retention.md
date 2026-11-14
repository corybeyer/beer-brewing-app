# ADR-0014: Transactional conversion proposal retention

Status: Proposed — November 9, 2026

## Context

C2b has immutable domain snapshots but no durable retention. A pre-save revision check alone cannot prevent a concurrent recipe edit. CV-08/CV-09/CV-12 require exact historical inputs, atomic conflict handling, and migration/restore evidence before release.

## Proposed decision

Add an append/load domain port and PostgreSQL adapter. Migration `0004_conversion_proposals` adds one append-only table with relational proposal ID, owning recipe-version FK, original edit revision, explicit creation time, format version, and a bounded, strictly encoded JSONB snapshot. This is a versioned historical document of defined domain fields, not an arbitrary recipe-edit blob. Live recipes and catalogue profiles keep their normalized owning schemas. The snapshot copies complete original/proposed plans, product profiles, exact numeric assumptions/results, and explanations so future live edits cannot reinterpret history.

Use a closed codec with explicitly registered domain types, strict fields, decimal strings, rational numerator/denominator strings, ISO timestamps, and ordered tuples. Reject unknown types/formats, malformed or excessive nesting, NUL, non-finite/unsupported numbers, and documents above 4 MiB. Decode and run domain validation on every load. SQL checks tie document headers to relational columns. No pickle, arbitrary imports, floating-point quantities, lossy decimal rounding, or remote fetch is used.

Append validates the snapshot, holds the owning draft's shared row lock, loads all current recipe children on that connection, and compares the complete original plus edit revision before inserting. Existing recipe saves use an exclusive lock on that same row. Check retained catalogue profiles against authoritative immutable revisions in the same transaction. Insert nothing on stale input, inconsistent product copies, duplicate ID, or failure. Load reads retained history independently of the current recipe/catalogue. Apply takes the exclusive recipe-version lock, checks the expected revision and complete original snapshot, validates the proposed plan, replaces plan rows, and increments the shared edit revision in one transaction. Stale and repeated Apply requests change nothing. Publication and physical brew actions remain outside this adapter.

Empty downgrade locks the proposal table and refuses populated data. Advance readiness and the explicit forward-only deployment policy together. Include populated proposals in snapshot fingerprints and real rollout/restore coverage. The administrator must install/verify reviewed operations from the exact clean PR commit before this schema release merges. Unknown/reverse/mismatched pairs remain rejected; incompatible prior APIs use retained-smoke recovery. No live downgrade or restore is performed on application rollback.

## Alternatives and consequences

Splitting every historical field into more live relational tables would duplicate existing models without a proposal query requirement. Storing only IDs loses independent historical interpretation. Unversioned/unvalidated JSON weakens integrity. The chosen document has closed typed meaning and a relational owner, but SQL does not reimplement every domain graph/calculation invariant; writes must use the port. C3/C4 blends and step adaptation require a deliberate format extension. ADR-0013 remains proposed and records the preceding domain snapshot contract.

## References

- [Proposal snapshot rules](../../requirements/conversion-proposal-snapshots.md)
- [Catalogue storage](../fermentable-catalogue.md)
- [Draft storage](../recipe-draft-storage.md)
- [Snapshot backups and rollout](0010-recipe-rollout-and-snapshot-backups.md)
