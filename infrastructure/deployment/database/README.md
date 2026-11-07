# Database roles and credentials

M1 infrastructure under [ADR-0004](../../../docs/architecture/decisions/0004-database-roles-and-secrets.md). No application login accounts are created. Root `app.py`, the production Dockerfile, and the Pi's root-owned configuration remain unchanged.

| Role | Purpose | Permissions |
| --- | --- | --- |
| `brewery_admin` | Database initialization and explicit provisioning | Bootstrap administrator; never used by the API/migrator |
| `brewery_migrator` | Alembic and feature grants | CONNECT and ownership of application `public` schema; no superuser, database creation, or role creation |
| `brewery_app` | API queries and future application data | CONNECT, schema USAGE, SELECT on `alembic_version`; future business-table access requires explicit grants |

Both non-admin roles have NOINHERIT and no role memberships. PUBLIC database/schema rights are revoked. Future migrations must grant required table and sequence permissions explicitly; PostgreSQL default privileges do not automatically give the application table access. See [PostgreSQL privileges](https://www.postgresql.org/docs/17/ddl-priv.html).

## Development

Run `python3 scripts/development/create_secrets.py`, then `docker compose up --build -d`. The generated `.secrets/` directory is owner-only and excluded from Git/build contexts. Passwords are not displayed. Repeating the generator preserves files, and repeating provisioning preserves existing PostgreSQL passwords.

The database starts before the provisioner; the migrator waits for provisioning; the API waits for migration success. Password files are mounted read-only per service. The provisioner alone can see administrator, migrator, and application passwords. No production passwords are stored in GitHub: GitHub Actions has independent disposable test credentials.

## Explicit host commands

For an existing development PostgreSQL instance, set a password-free `DATABASE_URL` and its `DATABASE_PASSWORD_FILE` in the environment. To provision, use administrator credentials and additionally set `MIGRATOR_PASSWORD_FILE` and `APPLICATION_PASSWORD_FILE`:

```sh
.venv/bin/python -m infrastructure.deployment.database.manage provision
```

This creates `brewery_migrator`/`brewery_app` and grants access in the selected application database. The database must already exist; the provisioner does not create it. It fails transactionally if an existing selected role has elevated flags or memberships. Existing passwords are not changed. New role passwords are encoded as SCRAM verifiers before the role DDL is sent to PostgreSQL.

Next change the environment to the migrator's URL and password file, and run:

```sh
.venv/bin/python -m infrastructure.deployment.database.manage migrate
```

This upgrades Alembic and grants the application read-only access to migration metadata in one transaction. A failed grant rolls back the upgrade. Use this wrapper for the application deployment; plain Alembic commands are lower-level tools and do not add the runtime metadata grant. `MIGRATION_ROLE` and `APPLICATION_ROLE` can override role names for isolated tests or operator-selected installations.

Start the API with the application's URL/password file. Never run it using the administrator or migration URL.

## Production adoption and recovery

The production database has not been provisioned by this change. Before adoption, the operator must create the application database and three independent host-held credential files, choose ownership/permissions for the intended container users, and wire only the appropriate read-only mounts into the Pi's separately reviewed Compose configuration. Production passwords stay on the Pi, outside the checkout; they do not need to pass through GitHub Actions. Secure copies used for recovery must follow the chosen backup/retention policy (D-06).

Do not use development credentials in production. File-backed Compose secrets are not an encrypted vault. Restrict parent-directory access and verify access from the intended container UID before deployment.

For an existing volume, take and verify a backup and inspect ownership/clients before provisioning; the script does not reassign existing tables/sequences. The old single-role development volume may still use `brewery` as administrator, and simply changing `POSTGRES_USER` does not rename it. Do not delete a volume to fix ownership or authentication problems.

Password rotation is explicit: an administrator changes a role password using an interactive password prompt (for example, psql's `\password`), updates its host file through the operator's secure workflow, and restarts affected services to clear old connections. Changing/generating a file alone never changes a saved PostgreSQL password. Keep the previous credentials securely available until the change is verified.

Application-image rollback does not reverse grants or ownership. The runtime deliberately remains restricted during rollback; reverting to the old administrator-sharing configuration is not an automatic rollback path. Schema downgrade/restore procedures remain migration-specific.
