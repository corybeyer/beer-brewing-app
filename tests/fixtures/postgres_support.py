"""Disposable PostgreSQL fixture shared by integration suites."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic.config import Config
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text

from brewery_config import database_url


ROOT = Path(__file__).resolve().parents[2]


class PostgreSQLTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = os.environ.get("TEST_DATABASE_URL")
        if not raw:
            raise unittest.SkipTest("Set TEST_DATABASE_URL to run real PostgreSQL integration tests")
        admin_url = database_url(raw)
        cls.admin = psycopg.connect(
            admin_url.set(drivername="postgresql").render_as_string(hide_password=False),
            autocommit=True,
            connect_timeout=3,
        )
        cls.addClassCleanup(cls.admin.close)
        cls.name = "brewery_test_" + uuid4().hex
        cls.admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.name)))
        cls.addClassCleanup(
            cls.admin.execute,
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(cls.name)),
        )
        cls.url = admin_url.set(database=cls.name)
        cls.engine = create_engine(cls.url)
        cls.addClassCleanup(cls.engine.dispose)

    def setUp(self):
        # This schema belongs to the generated database, never the supplied admin DB.
        with self.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        self.environment = patch.dict(os.environ, {
            "DATABASE_URL": self.url.render_as_string(hide_password=False),
            "DATABASE_PASSWORD_FILE": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.config = Config(str(ROOT / "alembic.ini"))
