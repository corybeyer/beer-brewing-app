"""HTTP failure behavior; database success is tested against PostgreSQL."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from brewery.api import create_app


class ApiTests(unittest.TestCase):
    def test_liveness_survives_database_failure_and_readiness_hides_details(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:secret@localhost/brewery"}):
            with TestClient(create_app()) as client:
                with patch.object(
                    client.app.state.database,
                    "connect",
                    side_effect=OperationalError("SELECT", {}, Exception("secret connection details")),
                ):
                    self.assertEqual(client.get("/health").json(), {
                        "status": "ok", "service": "beer-brewing-app",
                    })
                    response = client.get("/api/v1/readiness")
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json(), {"status": "unavailable"})

    def test_versioned_openapi_declares_readiness_failure(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/brewery"}):
            with TestClient(create_app()) as client:
                response = client.get("/api/v1/openapi.json")
                self.assertEqual(response.status_code, 200)
                operation = response.json()["paths"]["/api/v1/readiness"]["get"]
                self.assertIn("503", operation["responses"])
                self.assertEqual(client.get("/").status_code, 404)
