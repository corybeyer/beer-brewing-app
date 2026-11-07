"""Validate the retained version 1 sensor contract independently of storage/UI."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class SensorContractTests(unittest.TestCase):
    def test_sensor_contract_is_json(self):
        schema = json.loads((ROOT / "packages/communications/contracts/sensors/reading.schema.json").read_text())
        self.assertEqual(schema["title"], "SensorReadingV1")
        for key in ("measured_at", "received_at", "quality"):
            with self.subTest(key=key):
                self.assertIn(key, schema["required"])
