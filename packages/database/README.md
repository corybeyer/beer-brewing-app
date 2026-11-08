# Database

Owns PostgreSQL connections/schema readiness (`src/brewery_database/connection.py`) and versioned Alembic migrations (`migrations/`). It depends on database tooling, not FastAPI, UI, or deployment scripts. `brewery_database.recipes.PostgresRecipeDraftStore` implements the domain draft storage port with transactional create/load/replace and optimistic edit revisions.

Cluster-level role provisioning stays in `infrastructure/deployment/database/`; environment/credential parsing stays in `packages/config/`. The development migration `0002_recipe_drafts` adds six version-scoped draft plan tables. See [schema, permissions, transactions, and downgrade limits](../../docs/architecture/recipe-draft-storage.md). Production remains at baseline; the new revision requires reviewed rollout compatibility before merge/deployment. See the [backend foundation](../../docs/architecture/backend-foundation.md).
