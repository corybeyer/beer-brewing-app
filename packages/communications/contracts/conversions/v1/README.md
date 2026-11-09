# Fermentable conversion v1

`POST /api/v1/conversions/fermentable` is a pure calculator: no database access, catalogue inference, recipe write, or external request. It uses the existing exact C1 domain core.

- [Request schema](request.schema.json): strict decimal-string source mass, source/target yield/recovery/comparison-point/provenance, and target unit. Units: g/kg/oz/lb. Comparison points: kettle/fermenter. Both yields and both points must be explicit and compatible.
- [Response schema](response.schema.json): retained request assumptions, exact rational mass and gravity points × US gallons as decimal integer numerator/denominator strings, target unit, calculation version, and server-formatted display amount.
- [Error schema](error.schema.json): structured error code, message, and field issues (`path`, `code`, `message`). Invalid JSON is 400; invalid conversion/strict model input is 422. The browser boundary also returns 403/413/415 for forbidden origin/host, excessive request size, or unsupported media.

Decimal strings use ordinary notation (no exponents, signs, whitespace, JSON numbers, or non-finite values), up to 13 integer and 12 fractional places; the core additionally enforces at most 24 digits and magnitude below 10^13. Recovery must be positive and at most one. Provenance must be nonblank, NUL-free, and at most 1,000 characters per side. The unchanged shared 32 KiB body limit fits maximum fully escaped notes.

`display_decimal_places` is 6. `display_amount` uses HALF_UP rounding and exactly six fractional digits, except the literal `<0.000001` when a positive result would display as zero. It is display text, never an arithmetic input. Exact rational fields remain authoritative; conversion version is `gravity-equivalence/v1`. A small rounded display does not mean a missing or zero mass.

All responses use `Cache-Control: no-store`. OpenAPI is generated at `/api/v1/openapi.json`; schema parity tests compare checked-in JSON with actual transport models. No source/default yield, recovery, or flavor equivalence is implied.
