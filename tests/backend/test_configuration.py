"""Configuration failures never fall back to another database or leak secrets."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from brewery.config import database_url


class ConfigurationTests(unittest.TestCase):
    def test_password_file_supports_reserved_url_characters(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            path.write_text("p@ss:%word/with?characters\n")
            with patch.dict(os.environ, {
                "DATABASE_URL": "postgresql://brewer@localhost/brewery",
                "DATABASE_PASSWORD_FILE": str(path),
            }, clear=True):
                self.assertEqual(database_url().password, "p@ss:%word/with?characters")

    def test_file_errors_are_sanitized_and_do_not_fall_back(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            for content in (None, "", "first\nsecond", "bad\x00value"):
                with self.subTest(content=content):
                    if content is not None:
                        path.write_text(content)
                    with patch.dict(os.environ, {
                        "DATABASE_URL": "postgresql://brewer@localhost/brewery",
                        "DATABASE_PASSWORD_FILE": str(path),
                    }, clear=True):
                        with self.assertRaises(ValueError) as error:
                            database_url()
                        self.assertNotIn(str(path), str(error.exception))

    def test_conflicting_password_sources_are_rejected(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://brewer:secret@localhost/brewery",
            "DATABASE_PASSWORD_FILE": "/not/read",
        }, clear=True):
            with self.assertRaisesRegex(ValueError, "either URL or file"):
                database_url()

    def test_postgresql_url_uses_psycopg_and_preserves_encoded_password(self):
        url = database_url("postgresql://brewer:p%40ss%25word@localhost/brewery")
        self.assertEqual(url.drivername, "postgresql+psycopg")
        self.assertEqual(url.password, "p@ss%word")

    def test_missing_configuration_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
                database_url()

    def test_invalid_database_urls_are_rejected_without_echoing_input(self):
        for value in ("", "sqlite:///private.db", "postgresql://user:secret@host", "secret"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as error:
                    database_url(value)
                self.assertEqual(str(error.exception), "DATABASE_URL must name a PostgreSQL database")
