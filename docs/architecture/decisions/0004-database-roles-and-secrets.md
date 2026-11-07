# ADR-0004: Separate database roles and host-held credentials

Status: Accepted — November 7, 2026

## Context

The brewer requested separate migration/application roles and credentials outside Git. The M1 development stack previously used its bootstrap superuser for every connection. Production database passwords do not need to pass through GitHub Actions.

## Decision

- Keep a bootstrap administrator (`brewery_admin`) for provisioning only. Create a schema-owning `brewery_migrator` and a restricted `brewery_app`, both without superuser, database/role creation, replication, bypass-RLS privileges, or inherited role memberships.
- Give the migrator ownership of `public` in the application database, but not ownership of the database or administrator role. Revoke PUBLIC database access and schema permissions. Grant the application CONNECT and schema USAGE only.
- Grant the application SELECT on Alembic's version table after migrations, in the same transaction. Business-table access is granted explicitly by owning feature migrations; do not grant broad default table permissions or write access to migration metadata.
- Provision roles through an explicit infrastructure command before migrations. Repeat provisioning preserves existing passwords and fails on unexpected role privileges/memberships instead of silently repurposing privileged accounts. Password rotation is a separate operator action.
- Store three independently generated passwords in host files, excluded from Git and Docker build contexts. Development Compose mounts only the password each service needs. The bootstrap service alone receives all three. The API and migrator never receive administrator credentials.
- The application reads its password from `DATABASE_PASSWORD_FILE` and builds the SQLAlchemy URL in memory. Environment configuration contains role/host/database and a file path, not the password. Existing direct DATABASE_URL support remains for CI/host use; conflicting sources fail closed.
- GitHub CI uses only disposable test credentials. Production credentials remain on the Pi in operator-managed files and are not committed or uploaded to GitHub. Production provisioning/deployment is not performed by this change.

## Consequences

This extends [ADR-0003](0003-postgresql-foundation.md) within M1. It supports later UI-01–UI-06 and AC-01–AC-14 without completing any brewing acceptance scenario or implementing app login accounts (D-07).

Compose file secrets are read-only mounts, not encrypted secret storage. Development secret directories are owner-only; files are readable through their explicitly granted mounts by the non-root container user. Production operators must choose host ownership/permissions that permit intended containers to read only assigned files. Existing volumes require explicit provisioning; changing a file does not rotate an existing PostgreSQL password.

No business-table migration is introduced. Migrations remain versioned separately from cluster-level role provisioning. Before applying to an existing production database, take a verified backup, inspect existing object ownership/privileges, and review affected clients. Application rollback does not restore prior role grants; no automated privilege-widening rollback is provided.
