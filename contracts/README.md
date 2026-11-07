# Contracts

Formal versioned contracts belong here: OpenAPI requests/responses, internal events, and sensor payload schemas.

The development backend generates its version 1 OpenAPI contract at `/api/v1/openapi.json`. Health and database/schema readiness semantics are documented in the [backend foundation](../docs/architecture/backend-foundation.md#health-and-api-contract) and covered by HTTP tests. No brewing API is implemented yet.

The preliminary sensor reading schema includes device identity, measured and received timestamps, units, optional value, and quality state. It is not yet backed by a running sensor service. Schema compatibility changes require tests and documented migrations.
