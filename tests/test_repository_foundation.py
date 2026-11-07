"""Guard repository standards without requiring new third-party packages."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryFoundationTests(unittest.TestCase):
    def test_codex_instructions_exist(self):
        for path in ("AGENTS.md", "app/AGENTS.md", "web/AGENTS.md", "infra/AGENTS.md"):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())

    def test_sensor_contract_is_json(self):
        path = ROOT / "contracts/sensors/reading.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["title"], "SensorReadingV1")
        self.assertIn("measured_at", schema["required"])
        self.assertIn("received_at", schema["required"])
        self.assertIn("quality", schema["required"])

    def test_shared_design_tokens_exist(self):
        tokens = (ROOT / "web/src/design-system/tokens/tokens.css").read_text(encoding="utf-8")
        for token in ("--color-text:", "--color-background:", "--font-family-body:", "--space-4:"):
            with self.subTest(token=token):
                self.assertIn(token, tokens)


if __name__ == "__main__":
    unittest.main()
