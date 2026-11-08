"""Real PostgreSQL integration tests; create/drop only a generated test database."""

import os
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from brewery_api.api import create_app
from brewery_database.connection import SCHEMA_REVISION
from tests.fixtures.postgres_support import PostgreSQLTestCase


class PostgreSQLTests(PostgreSQLTestCase):
    def test_upgrade_is_repeatable_and_migrated_api_is_ready(self):
        command.upgrade(self.config, "head")
        command.upgrade(self.config, "head")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(), SCHEMA_REVISION)
            tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars().all()
            self.assertEqual(set(tables), {"alembic_version", "recipe", "recipe_version", "recipe_ingredient",
                                           "recipe_step", "recipe_step_dependency", "recipe_step_addition"})
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/readiness")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ready"})

    def test_startup_does_not_migrate_unversioned_database(self):
        with TestClient(create_app()) as client:
            self.assertEqual(client.get("/api/v1/readiness").status_code, 503)
            self.assertEqual(client.get("/health").status_code, 200)
        with self.engine.connect() as connection:
            self.assertIsNone(connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar_one())

    def test_unexpected_schema_revision_is_not_ready(self):
        command.upgrade(self.config, "head")
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = 'unknown_revision'"))
        with TestClient(create_app()) as client:
            self.assertEqual(client.get("/api/v1/readiness").status_code, 503)

    def test_missing_database_reports_unavailable_without_driver_details(self):
        missing = self.url.set(database="brewery_missing_" + uuid4().hex)
        with patch.dict(os.environ, {"DATABASE_URL": missing.render_as_string(hide_password=False)}):
            with TestClient(create_app()) as client:
                response = client.get("/api/v1/readiness")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"status": "unavailable"})
                self.assertEqual(client.get("/health").status_code, 200)

    def test_baseline_round_trip_preserves_populated_existing_table(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE retained_fixture (note text NOT NULL)"))
            connection.execute(text("INSERT INTO retained_fixture VALUES ('preserve me')"))
        command.upgrade(self.config, "head")
        command.downgrade(self.config, "base")
        with TestClient(create_app()) as client:
            self.assertEqual(client.get("/api/v1/readiness").status_code, 503)
        command.upgrade(self.config, "head")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT note FROM retained_fixture")).scalar_one(), "preserve me")
