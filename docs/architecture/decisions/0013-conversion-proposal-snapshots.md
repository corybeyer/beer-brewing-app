# ADR-0013: Immutable conversion proposal inputs

Status: Proposed — November 8, 2026

## Context

C2b of the extract-conversion plan needs to preserve the original recipe and the reviewed proposal independently of later recipe/catalogue edits. C1 supplies exact single-fermentable conversions and C2a supplies immutable product revisions. Neither establishes proposal persistence or permission to apply a change.

## Proposed decision

Begin with pure, immutable domain snapshots for explicit one-to-one ingredient substitutions. Retain the complete original draft and edit revision, complete proposed draft, creation timestamp, full selected catalogue revisions (including referenced grain components), conversion results with versioned arithmetic and yield/recovery provenance, explicit potential overrides, and weighing explanations. Recompute C1 evidence before trusting it. Preserve unknown draft fields and unrelated metadata, ingredient order, steps, and addition links. Changed ingredient rows require corresponding calculation evidence. Rounded weighing/portion amounts require an explanation; exact results remain separate.

A pure revision guard compares both the original edit revision and complete draft with a newly loaded current draft. This can detect a stale review but cannot close a race with a later write. A future database adapter must retain proposals transactionally against the expected recipe revision, and a future Apply transaction must check again. No domain helper writes, publishes, starts brewing, or authorizes physical actions.

This first slice adds no schema, persistence adapter, HTTP/UI contract, or proposal-store port. Define the transactional retention contract alongside its implementation. Blend/ranking generation and step adaptation remain C3/C4; extend the proposal format deliberately when those rules exist rather than treating a single-target calculation as a blend.

## Alternatives and consequences

Storing only catalogue IDs would make interpretation depend on future catalogue availability. Storing only displayed decimals would lose recurring exact results. Capturing arbitrary proposed edits without calculation/link checks would let unrelated changes masquerade as a conversion. Snapshot validation therefore checks the C1 substitution evidence while allowing explained weighing adjustments. It does not establish flavor equivalence, mash feasibility, publication readiness, durable retention, or concurrent application safety.

## References

- [Conversion plan and CV-08/CV-09/CV-12](../../plan/extract-conversion.md)
- [Catalogue storage](../fermentable-catalogue.md)
- [Recipe-plan validation](../../requirements/recipe-plan-validation.md)
