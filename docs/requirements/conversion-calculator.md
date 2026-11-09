# Standalone fermentable conversion calculator

C5 first slice, supporting M2 ingredient planning and M6 reviewed adaptation; CV-01–CV-04 and CV-11. [Proposed ADR-0016](../architecture/decisions/0016-standalone-conversion-calculator.md) records the boundary.

The calculator requires source mass/unit, source and target PPG potential, both recovery fractions, both comparison points, both provenance explanations, and target mass unit. No product/recovery values are inferred or supplied as defaults. Comparison points must match. Mass units are g/kg/oz/lb; volume units are unsupported. The backend reuses C1 exact arithmetic and explicit provenance rules. Matching gravity contribution does not establish flavor, fermentability, color, enzyme sufficiency, publication readiness, or an equipment action.

`POST /api/v1/conversions/fermentable` consumes bounded plain decimal strings, rejects unknown fields, and returns exact rational amount/gravity contribution plus the original assumptions and calculation version. Server display uses HALF_UP rounding to six decimal places; a positive value below display resolution that would round to zero is shown as `<0.000001`, never a trustworthy zero. The exact numerator/denominator remains available. The browser does no brewing arithmetic and labels display rounding.

Provenance is nonblank/NUL-free text up to 1,000 characters each. The shared local browser boundary keeps its 32 KiB request cap; both maximum notes fit even with JSON-escaped supplementary Unicode. Host/origin/Fetch Metadata, JSON media, UTF-8, declared and streamed body limits apply before parsing. Responses have `Cache-Control: no-store`. No authentication/network exposure is added. The endpoint uses no database connection or write and remains usable when database readiness is unavailable.

The responsive page provides labeled fields, explicit units/measurement bases, keyboard access, busy/error feedback, retained entered values on errors, and a clear result with exact values and retained assumptions. Conversion results are advisory. Efficiency tools, catalogue matching, proposal persistence, recipe Apply, and other calculators remain later slices.

Backend tests cover exact sourced arithmetic, explicit/missing/invalid assumptions, strict fields and decimal strings, boundary/media/origin/size behavior, maximum escaped Unicode notes, tiny/large valid display output, OpenAPI/schema parity, preserved recipe-validation behavior, and success during database failure. UI/browser evidence is tracked with the owning frontend slice and source-bound pre-PR report.
