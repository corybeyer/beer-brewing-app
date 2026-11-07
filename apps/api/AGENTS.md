# Backend instructions

- Keep FastAPI composition in `apps/api/brewery_api/`; brewing rules/ports belong in `packages/domain/` and adapters in their owning packages.
- Keep pure business rules isolated from HTTP, database, and telemetry transports.
- Integrations are adapters behind explicit contracts/ports.
- Store UTC measurement and ingestion timestamps separately.
- Mark missing/stale/outlier readings before offering recommendations.
- Keep operational decisions advisory; never infer that a manual brewing step occurred simply because a temperature or timer reached a threshold.
- Introduce FastAPI, SQLAlchemy, and Alembic only with runnable tests and versioned migrations.
- Persistence and migrations live in `packages/database/`; credentials/configuration in `packages/config/`. Never import deployment/provisioning scripts into application runtime.
