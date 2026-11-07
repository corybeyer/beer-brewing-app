# Backend instructions

- Organize code around brewing capabilities under app/modules/.
- Keep pure business rules isolated from HTTP, database, and telemetry transports.
- Integrations are adapters behind explicit contracts/ports.
- Store UTC measurement and ingestion timestamps separately.
- Mark missing/stale/outlier readings before offering recommendations.
- Keep operational decisions advisory; never infer that a manual brewing step occurred simply because a temperature or timer reached a threshold.
- Introduce FastAPI, SQLAlchemy, and Alembic only with runnable tests and versioned migrations.
