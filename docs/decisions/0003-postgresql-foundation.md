# ADR-0003: PostgreSQL backend foundation

Status: Accepted — November 7, 2026

## Context

M1 needs persistence and a runnable backend without replacing the production smoke service. The brewer selected PostgreSQL instead of the previously proposed SQLite foundation. No active application database needs migration.

## Decision

- Use PostgreSQL 17 for the first foundation, with SQLAlchemy 2, Psycopg 3, and Alembic. Pin the major database version; test upgrades explicitly.
- Build the FastAPI backend as package `brewery` under `app/brewery/`. The ASGI factory is `brewery.api:create_app`. Installing the package avoids the root `app.py`/directory naming conflict.
- Keep root `app.py`, root Dockerfile, and the production publication/deployment workflow in place until controlled replacement is separately validated.
- Provide an isolated development Compose stack. PostgreSQL has no published host port; the development API binds to localhost on port 8081. Database files live in a named volume.
- Run migrations explicitly in a one-shot service, never implicitly on API startup. Readiness requires connectivity and the expected Alembic revision; liveness retains the existing `/health` payload.
- Start with a baseline migration that establishes Alembic version tracking only. Introduce domain tables with their owning features instead of creating the entire target ERD.
- Keep non-secret database connection settings in environment configuration and load passwords from assigned files, as specified by [ADR-0004](0004-database-roles-and-secrets.md). Domain modules must not import SQLAlchemy, Psycopg, or FastAPI.
- Use PostgreSQL for integration tests. Isolate tests in a disposable database/schema; do not substitute SQLite.

## Alternatives

SQLite would reduce operational work but was not selected. Introducing all 31 target entities now would impose unvalidated feature decisions. Replacing the production container now would bypass the controlled deployment requirement.

## Consequences

The database is a separate stateful service requiring credentials, backups, and planned upgrades. Application-image rollback cannot reverse database changes. Before any future production migration, take and verify a logical backup, review compatibility with the previous application, and test restoration. Backup destination, schedule, and retention remain D-06 work; this foundation does not complete AC-14.

The baseline has no business data to transform. Its downgrade removes Alembic revision state only. Later feature migrations must test upgrade from populated prior revisions and explicitly document downgrade/data-loss behavior.

D-01 backend/entrypoint and the tooling portion of D-03 are settled by this record. Frontend design tooling (D-02), feature contracts, publication rules, and detailed field semantics remain separate decisions. This supports M1 and future UI-01–UI-06/AC-01–AC-14; no brewing acceptance scenario is complete merely because the foundation exists.
