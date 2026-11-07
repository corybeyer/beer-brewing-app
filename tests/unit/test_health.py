"""Basic service contract smoke test."""
import unittest

from app import health_payload


class HealthTests(unittest.TestCase):
    def test_health_payload(self):
        self.assertEqual(
            health_payload(),
            {"status": "ok", "service": "beer-brewing-app"},
        )


if __name__ == "__main__":
    unittest.main()
