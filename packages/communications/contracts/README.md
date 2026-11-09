# Contracts

Formal versioned contracts belong here: OpenAPI requests/responses, internal events, and sensor payload schemas.

The development backend generates its version 1 OpenAPI contract at `/api/v1/openapi.json`. Health and database/schema readiness semantics are documented in the [backend foundation](../../../docs/architecture/backend-foundation.md#health-and-api-contract) and covered by HTTP tests. The [v1 recipe overview contract](recipes/v1/README.md) now defines draft creation/list/read and overview-only save with explicit revision/errors; publication and brewing execution APIs remain unavailable.

The preliminary sensor reading schema includes device identity, measured and received timestamps, units, optional value, and quality state. It is not yet backed by a running sensor service. Schema compatibility changes require tests and documented migrations.

The [v1 standalone fermentable conversion contract](conversions/v1/README.md) defines explicit inputs, exact rational results, server-only display rounding, and field errors without database dependence.
