# ADR-0015: Explainable grain matches and exact blend sizing

Status: Proposed — November 9, 2026

## Context

C3 must present a closest match first while keeping optional flavor variations separate (CV-05/CV-06/CV-10). C2a provides immutable sourced catalogue profiles. Those profiles do not establish equipment recovery, mash feasibility, or finished-beer equivalence. The first C3 slice should rank supplied evidence without guessing an unknown extract bill.

## Proposed decision

Add a pure ranking function over one validated DME/LME source revision and an explicitly supplied tuple of grain revisions. If every component of the source's complete grain bill resolves, return that retained bill first, labeled as manufacturer-reported or manually assumed composition. Never describe a manual assumption as a verified manufacturer match. An unknown or unresolved bill supplies no composition-match option.

Offer optional single-grain variations separately. Rank them by exact Jaccard similarity of source-reported descriptor tags, then availability of comparable color evidence, then exact gap between color ranges, then revision ID. Compare colors only with identical declared unit and measurement basis; do not convert units, compare concentrations to dry grain, average ranges, or infer finished-beer color. Missing evidence remains absent rather than a perfect numeric match. Preserve full source and grain revisions, shared tags, scores, review reasons, and a ranking version for explanation.

Ranking requires explicit recovery input, mash-feasibility review, and whole-recipe mash/boil/hop-balance review. It does not calculate mass or invent blends. A separate pure blend calculator sizes a caller-selected tuple of complete grain profiles with exact mass shares, explicit yield/recovery/comparison-point assumptions, and notes for missing/overridden catalogue potentials. Reuse C1's unit/contribution calculation, compute the exact mass-weighted yield, and return exact rational total/component masses and gravity contributions under `grain-blend-gravity/v1`. Preserve the full selected profiles and assumptions. Share totals are exact and must equal one; no weighing rounding occurs.

Neither function reads a database, calls a remote source, mutates a recipe, or establishes readiness. Proposal/API integration remains later C3 work; explicit preview/apply remains C4. The supplied grain set is an input selection, not an automatic newest-revision policy. The current C2b proposal format supports one-to-one C1 evidence and does not yet retain this blend result; extending it requires a deliberate format change.

## Alternatives and consequences

Claiming an exact grain bill from color alone fabricates composition. One opaque weighted flavor score obscures missing data. Expanding into all possible blends before validating a matching contract would increase scope without reliable enzyme/process data. The first slice therefore provides explainable candidates and evidence only, with strict validation and deterministic tie-breaks. It does not seed a manufacturer catalogue or promise identical flavor.

## References

- [Conversion plan and checks](../../plan/extract-conversion.md)
- [Catalogue provenance rules](../fermentable-catalogue.md)
- [Layer boundaries](../dependency-rules.md)
