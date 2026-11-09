# ADR-0016: Standalone fermentable conversion calculator

Status: Proposed — November 9, 2026

## Context

C5 can expose the already tested C1 conversion core before catalogue matching or proposal Apply is available. The calculator must retain explicit assumptions, work without database availability, and avoid duplicating brewing arithmetic in the browser.

## Proposed decision

Add a responsive calculator page backed by `POST /api/v1/conversions/fermentable`. Require decimal-string source mass, both PPG/recovery/comparison-point/provenance inputs, and target mass unit. Call only the existing pure C1 core. Return exact rational mass/gravity contribution, retained input assumptions, calculation version, and server-formatted display text. Display uses six decimal places with explicit HALF_UP rounding; a positive result that would round to zero is represented as `<0.000001`. The exact rational result remains authoritative. No default yields/recovery, catalogue lookup, database write, remote calculator request, recipe application, or physical action occurs.

Reuse the existing host/origin/Fetch Metadata/UTF-8/JSON request boundary with a conversion route prefix and the unchanged 32 KiB cap. Bound provenance to 1,000 characters each so the valid maximum fits even with fully escaped supplementary Unicode. Strict versioned request/response/error schemas and generated OpenAPI document the transport. Validation errors retain field paths. Browser code displays server results and keeps inputs on recoverable failures rather than implementing conversion math.

## Consequences

This implements only standalone fermentable conversion, not an equipment-efficiency calculator, a flavor-equivalence claim, mash feasibility, or the recipe picker. Database readiness may be unavailable while this pure calculator remains usable. No schema or installed-operations update is required. The existing production/runtime health path remains intact.

## References

- [Sourced conversion plan](../../plan/extract-conversion.md)
- [Calculator requirements](../../requirements/conversion-calculator.md)
- [Versioned conversion contract](../../../packages/communications/contracts/conversions/v1/README.md)
