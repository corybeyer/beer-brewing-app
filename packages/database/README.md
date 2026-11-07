# Database

Owns PostgreSQL connections/schema readiness (`src/brewery_database/connection.py`) and versioned Alembic migrations (`migrations/`). It depends on database tooling, not FastAPI, UI, or deployment scripts. Domain repository ports and feature models are added with their owning features.

Cluster-level role provisioning stays in `infrastructure/deployment/database/`; environment/credential parsing stays in `packages/config/`. No business tables exist yet. See the [backend foundation](../../docs/architecture/backend-foundation.md).
