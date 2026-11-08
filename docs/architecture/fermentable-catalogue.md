# Sourced fermentable catalogue storage

C2a of the [conversion plan](../plan/extract-conversion.md), M2/UI-04/UI-05 and M6 reviewed adaptations, under [proposed ADR-0012](decisions/0012-fermentable-catalogue.md). This is a development storage slice; there is no catalogue editor, remote fetch, recommendation endpoint, or automatic recipe conversion. C2b proposal/original-input snapshots remain separate work.

## Stored profile contract

`brewery_domain.fermentable_catalogue` defines frozen `CatalogRevision`, `IngredientColor`, `GrainComponent`, validation issues/exceptions, and the `FermentableCatalog` append/load port. A stable product ID has one kind: grain, dme, or lme. Revisions have globally unique IDs and unique positive numbers within a product. Names/manufacturer, source label, optional HTTP(S) source URL, and a timezone-aware retrieval timestamp belong to the revision, rather than a mutable product identity.

Potential is an optional exact Decimal PPG value on an as-supplied mass basis. `potential_status` distinguishes unknown, manufacturer, and manual_assumption. Unknown requires a missing potential; manufacturer claims require manufacturer identity and a source URL; manual assumptions require an explanatory note. Do not treat a laboratory dry-basis extract percentage as PPG or invent default yields. The C1 core still requires explicit recovery and a comparison point at calculation time; catalogue product yield is not equipment efficiency.

Optional color is a low/high Decimal range with a controlled unit (lovibond, srm, ebc) and nonblank measurement/concentration basis. Preserve the source range, rather than guessing a midpoint or equating an extract's color at a stated concentration to grain Lovibond or finished-beer SRM. Flavor notes and up to 32 unique, ordered lowercase tags describe source-reported character; they are not measured finished-beer scores or a guarantee of taste.

An extract can have a complete grain bill or unknown composition. `composition_status` uses the same three provenance categories; manual assumptions require an explanation. Up to 100 distinct components reference existing immutable grain revisions, with positive exact mass fractions totaling one. Shares describe the source grain bill by mass, not fractions of water/extract weight. Grain revisions cannot own extract bills; components cannot reference extracts, so nested cycles cannot form. Unsupported mixed/sugar compositions stay unknown and require review. Enzyme/mash feasibility is not established by these profiles.

Domain numeric input limits are 24 digits, at most 12 fractional places, and magnitude below 10^12 (zero is allowed only for color). Source URLs are optional provenance identifiers: HTTP(S), ASCII/Punycode DNS host or an IPv6 literal, optional valid port, and no whitespace/userinfo. No network request is performed. Typed values and source timestamps are required; missing data does not become zero or current time.

## Tables and transactions

`0003_fermentable_catalogue` follows `0002_recipe_drafts` and adds:

| Table | Ownership and constraints |
| --- | --- |
| fermentable_product | Stable ID and kind, with a composite unique key for kind-preserving revision references |
| fermentable_revision | Immutable profile/source fields; unique product/revision number; finite numeric values; complete color context; explicit provenance status; UTC-capable timestamps |
| fermentable_flavor | Ordered, unique descriptor tags owned by a revision, bounded to 32 positions |
| fermentable_component | Ordered grain revision references owned by an extract, bounded to 100 positions; composite FKs enforce source/target kinds |

`PostgresFermentableCatalog.append` validates the profile, checks referenced grain revisions, and writes identity/profile/children in one transaction. Duplicate revisions or product-kind changes raise `CatalogConflict`; invalid/incomplete bills raise field-specific `InvalidCatalogRevision`; driver failures become sanitized `CatalogUnavailable`. Failed writes leave no orphan product or partial children. Old revisions are never replaced. `load` returns a complete immutable profile or None; cross-record validation failures in stored data are unavailable, not trusted profiles.

Runtime SQL grants are SELECT/INSERT only for these four tables; UPDATE/DELETE/DDL and migration metadata writes remain denied. Application writes must use the port; bypassing it with raw SQL is unsupported. Local SQL checks/FKs enforce field/ownership invariants; complete-bill totals and other cross-record semantics are validated by the domain/adapter. Catalogue rows are independent of recipes in this slice: no recipe FK, snapshot, proposal, or published-history contract is introduced yet.

## Migration, backup, and release

Upgrade preserves populated recipe data and seeds no catalogue assumptions. Empty downgrade locks all four catalogue tables before checking emptiness, removes only those tables, and leaves recipes/revision `0002_recipe_drafts` intact. Any catalogue data refuses downgrade without changing its rows or metadata. No application rollback runs a schema downgrade or restores over live data.

Source readiness and operator heads advance to `0003_fermentable_catalogue`. The explicit deployment policy supports baseline -> recipe -> catalogue and same-revision adoption, rejects reverse/unknown/mismatched revisions, and verifies the resulting schema. A failed upgrade uses the previous API only if its declared schema matches the database; otherwise it retains PostgreSQL and serves the legacy smoke service. Snapshot backup fingerprints include all catalogue tables and compare the real scratch restore with one exported source snapshot.

Installed recipe-only operations do not accept the new revision. After the PR passes CI and its source is reviewed, an administrator must install updated operations from the exact clean reviewed commit **before this schema change merges**. The updater recognizes the retained baseline predecessor and the reviewed recipe operations hash `545c7bcf971327a054981c6bbdd6c228f5b048808d147d13f3a68bb1e04790f4`, preserves installation state/credentials, and retains the prior script. Follow the [catalogue rollout procedure](../../infrastructure/deployment/production/ROLLOUT.md#upgrading-installed-operations-before-the-catalogue-release). Ordinary main publication then deploys the matching application/operator pair. This document does not claim any root update or production migration has occurred.

## Verification scope

Unit tests cover missing values/provenance, exact component totals under low Decimal precision, color basis/ranges, URL/timestamp/descriptor validation, and unsupported data. Real PostgreSQL tests cover append/load, old-revision preservation, duplicate/concurrent writes, kind/foreign-key constraints, failed-write rollback, stored anomalies, populated recipe upgrade, empty/populated downgrade, runtime grants, and populated catalogue dump/restore. Source-bound full results belong in `.validation/pre-pr.json`; Docker/ARM64/rollout CI and actual host adoption remain separate evidence. This supplies storage-level support toward CV-05–CV-08/CV-12, not completed matching, preview/apply, or full acceptance.
