"""Verify privileges using real, separately authenticated PostgreSQL roles."""

import os
import secrets
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from brewery.api import create_app
from infra.database.manage import migrate, provision
from postgres_support import PostgreSQLTestCase, ROOT


class DatabaseRoleTests(PostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid4().hex
        self.migrator = "migration_" + suffix
        self.application = "application_" + suffix
        self.migration_password = secrets.token_hex(24)
        self.application_password = secrets.token_hex(24)
        self.addCleanup(self.cleanup_roles)
        self.provision_roles()

    def connect_as(self, role, password):
        return psycopg.connect(self.url.set(
            drivername="postgresql", username=role, password=password,
        ).render_as_string(hide_password=False), autocommit=True)

    def provision_roles(self):
        with self.connect_as(self.url.username, self.url.password) as connection:
            provision(connection, self.migrator, self.application,
                      self.migration_password, self.application_password)

    def cleanup_roles(self):
        with self.connect_as(self.url.username, self.url.password) as connection:
            for role in (self.application, self.migrator):
                exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
                if exists:
                    connection.execute(sql.SQL("DROP OWNED BY {} CASCADE").format(sql.Identifier(role)))
                    connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))

    def migrate_as_owner(self):
        migrate(self.url.set(username=self.migrator, password=self.migration_password),
                self.application, str(ROOT / "alembic.ini"))

    def test_migrator_runs_migrations_and_runtime_is_ready(self):
        self.migrate_as_owner()
        self.migrate_as_owner()
        with patch.dict(os.environ, {"DATABASE_URL": self.url.set(
            username=self.application, password=self.application_password,
        ).render_as_string(hide_password=False)}, clear=True):
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/api/v1/readiness").status_code, 200)
        with self.connect_as(self.migrator, self.migration_password) as connection:
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                connection.execute("CREATE ROLE forbidden_role")
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                connection.execute("CREATE DATABASE forbidden_database")

    def test_runtime_cannot_modify_schema_or_migration_metadata(self):
        self.migrate_as_owner()
        with self.connect_as(self.application, self.application_password) as connection:
            for statement in (
                "CREATE TABLE forbidden_table (value text)",
                "CREATE TEMP TABLE forbidden_temp (value text)",
                "ALTER TABLE alembic_version ADD COLUMN forbidden text",
                "DROP TABLE alembic_version",
                "UPDATE alembic_version SET version_num = 'forbidden'",
                "DELETE FROM alembic_version",
                "CREATE ROLE forbidden_role",
                "CREATE DATABASE forbidden_database",
            ):
                with self.subTest(statement=statement):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        connection.execute(statement)

    def test_failed_metadata_grant_rolls_back_migration(self):
        with self.assertRaises(ProgrammingError):
            migrate(self.url.set(username=self.migrator, password=self.migration_password),
                    "missing_" + uuid4().hex, str(ROOT / "alembic.ini"))
        with self.engine.connect() as connection:
            self.assertIsNone(connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar_one())

    def test_runtime_needs_explicit_business_table_grants(self):
        with self.connect_as(self.migrator, self.migration_password) as owner:
            owner.execute("CREATE TABLE fixture (id bigint GENERATED ALWAYS AS IDENTITY, note text)")
            with self.connect_as(self.application, self.application_password) as app:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    app.execute("SELECT * FROM fixture")
                owner.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON fixture TO {}").format(sql.Identifier(self.application)))
                owner.execute(sql.SQL("GRANT USAGE ON SEQUENCE fixture_id_seq TO {}").format(sql.Identifier(self.application)))
                app.execute("INSERT INTO fixture (note) VALUES ('recorded')")
                app.execute("UPDATE fixture SET note = 'corrected'")
                self.assertEqual(app.execute("SELECT note FROM fixture").fetchone()[0], "corrected")
                app.execute("DELETE FROM fixture")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    app.execute("DROP TABLE fixture")

    def test_reprovision_preserves_passwords_and_rejects_privileged_existing_roles(self):
        with self.connect_as(self.url.username, self.url.password) as admin:
            original = admin.execute("SELECT rolpassword FROM pg_authid WHERE rolname = %s", (self.application,)).fetchone()[0]
            self.provision_roles()
            self.assertEqual(admin.execute("SELECT rolpassword FROM pg_authid WHERE rolname = %s", (self.application,)).fetchone()[0], original)
            self.assertTrue(original.startswith("SCRAM-SHA-256$"))
            admin.execute(sql.SQL("ALTER ROLE {} CREATEDB").format(sql.Identifier(self.application)))
            with self.assertRaisesRegex(ValueError, "unexpected privileges"):
                self.provision_roles()

    def test_wrong_password_is_rejected_over_tcp(self):
        # TEST_DATABASE_URL must use TCP/SCRAM to exercise password authentication.
        if not self.url.host or self.url.host.startswith("/") or self.url.query.get("host", "").startswith("/"):
            self.skipTest("TCP PostgreSQL URL required for SCRAM authentication check")
        with self.assertRaises(psycopg.OperationalError):
            self.connect_as(self.application, "incorrect-test-password")
