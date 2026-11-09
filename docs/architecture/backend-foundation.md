# M1 backend and PostgreSQL foundation

Decisions: [ADR-0003](decisions/0003-postgresql-foundation.md) and [ADR-0004](decisions/0004-database-roles-and-secrets.md). Scope: backend and persistence portion of M1. No UI screens or brewing acceptance scenarios are completed by this foundation.

## Run locally with Compose

From the repository root, generate local development credentials, then start Compose:

```sh
python3 scripts/development/create_secrets.py
docker compose up --build -d
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8081/api/v1/readiness
```

The generator creates three independent password files in `.secrets/`, which is ignored by Git and excluded from Docker build contexts. It never prints or overwrites existing passwords. The directory is mode 0700. Files are mode 0444 so the non-root container can read an explicitly assigned read-only secret mount; other host users cannot traverse the parent directory. Keep the directory private and do not copy the passwords into chat, Git, or GitHub secrets. `.env.example` now contains only an optional directory path; no `.env` is required for the default location.

Startup order is database -> provision -> migrate -> backend. Provisioning uses `brewery_admin`; migrations use schema owner `brewery_migrator`; the API uses restricted `brewery_app`. Each service receives only its assigned files, with all three available only to the bootstrap provisioner. The API has no schema creation rights or write access to Alembic metadata. Future business-table privileges must be granted explicitly by their owning migrations. See [database operations](../../infrastructure/deployment/database/README.md).

PostgreSQL has no published host port; the API is exposed on localhost:8081. This is development configuration, not a replacement for the Pi's root-owned production files. Compose file secrets are bind mounts, not encrypted storage; see [Docker's file-secret guidance](https://docs.docker.com/compose/how-tos/use-secrets/).

Stop with `docker compose down`. The named volume survives container replacement and `down`. Do not use `down -v` for data you want to retain. Changing password files does not rotate existing database passwords. Existing volumes initialized under the previous `brewery` bootstrap user need explicit administrative review/provisioning; this change does not rename that user or migrate its owned objects automatically.

## Host development

Use Python 3.12 or newer and an existing PostgreSQL 17 instance:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
```

Set `DATABASE_URL` to the PostgreSQL role/host/database and `DATABASE_PASSWORD_FILE` to its local password file. Both `postgresql://` and `postgresql+psycopg://` select Psycopg 3; other databases are rejected. Password files support reserved URL characters without manual encoding; unreadable/empty files and simultaneous URL/file passwords are rejected. Direct URLs with percent-encoded credentials remain supported for tests. Host commands do not automatically load `.env`.

Provision roles first using the [operator commands](../../infrastructure/deployment/database/README.md). Then run migrations as the migrator and start the API as the application role, changing the environment between commands:

```sh
.venv/bin/python -m infrastructure.deployment.database.manage migrate
.venv/bin/python -m uvicorn brewery_api.api:create_app --factory --host 127.0.0.1 --port 8081
```

Python packages `brewery_api`, `brewery_database`, `brewery_config`, and `brewery_domain` have explicit source mappings in `pyproject.toml`; root `app.py` remains the independently runnable production smoke service. Migrations remain repository-owned under `packages/database/migrations/` and are included in the development image.

## Health and API contract

- `GET /health`: HTTP 200 and the original `{"status":"ok","service":"beer-brewing-app"}` payload. Liveness is independent of database availability.
- `GET /api/v1/readiness`: HTTP 200 `{"status":"ready"}` only when PostgreSQL responds with exactly the expected Alembic revision; otherwise HTTP 503 `{"status":"unavailable"}`. Never includes database error text or credentials. Connection, pool, and statement waits are bounded.
- `GET /api/v1/openapi.json`: generated version 1 contract, including the documented 503 response. Interactive documentation is at `/api/v1/docs`.

API startup requires valid configuration but does not connect eagerly, run migrations, or create tables. The initial `0001_baseline` migration establishes revision tracking without business tables. The development head is now `0002_recipe_drafts`, adding [draft recipe storage](recipe-draft-storage.md); production adopted that revision after the reviewed operations update and controlled automatic deployment; see [host evidence](../plan/status.md#verified-production-recipe-schema-adoption). Feature migrations must update the readiness revision and test upgrade from populated prior schemas. Schema equality is a version check, not a full audit of database permissions or schema corruption.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

For PostgreSQL integration tests, set `TEST_DATABASE_URL` to a disposable PostgreSQL instance with administrative permission to create/drop databases and roles. Tests create uniquely named databases and roles and clean them up; they never reset the supplied database. Use TCP with SCRAM authentication to exercise the wrong-password test; that check is explicitly skipped for Unix sockets. Snapshot backup integration tests also need PostgreSQL 17 client tools: set `POSTGRES_TEST_BIN` to their binary directory, or use clients already on PATH. CI supplies `TEST_POSTGRES_CONTAINER` from its disposable PostgreSQL service and runs those clients inside that service. A supplied test database with missing/mismatched tools fails rather than silently skipping snapshot verification. Without the database setting, integration classes are explicitly skipped. CI supplies PostgreSQL with TCP/SCRAM and runs these tests.

Tests cover configuration rejection, secret generation/non-overwrite behavior, health during database failure, sanitized readiness failures, missing/unexpected schema versions, explicit/repeated migrations, migration/grant atomicity, and preservation of a populated fixture across baseline upgrade/downgrade/upgrade. Role tests verify authenticated migration/readiness, denied runtime DDL/metadata writes, explicit business-table grants, password rejection, and safe repeat provisioning. The recipe integration suite separately validates `0002_recipe_drafts`, including populated-baseline upgrades, relational constraints, atomic saves, concurrency, and guarded downgrade. These suites do not establish AC-14 restoration.

## Migration and deployment safety

Before future production adoption, verify a logical backup/restore, choose backup location and retention (D-06), provision the separate roles and host-held secret mounts, and perform a controlled ARM64 deployment. Run migrations as a single explicit operation before starting the new application. Never run destructive downgrades automatically during application rollback.

The original baseline can be downgraded with `alembic downgrade base`; this removes revision state and leaves unrelated tables intact. From the recipe head, downgrade requires empty recipe tables and locks out concurrent writers; populated draft downgrade fails without data loss. Readiness then returns 503 until upgraded. Later migrations must document compatibility, retained data, and reversibility individually. A PostgreSQL major upgrade requires an explicit upgrade/restore procedure; changing the image tag alone is not sufficient.


The catalogue development slice advances source readiness/operator head to `0003_fermentable_catalogue`. Installed production revision is separate evidence; review [catalogue storage](fermentable-catalogue.md) and complete its guarded operations update before merging/deploying this revision. No migration runs implicitly on API startup.
