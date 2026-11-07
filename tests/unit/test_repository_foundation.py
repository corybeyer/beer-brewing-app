"""Guard repository standards without requiring new third-party packages."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class RepositoryFoundationTests(unittest.TestCase):
    def test_codex_instructions_exist(self):
        for path in ("AGENTS.md", "apps/api/AGENTS.md", "apps/web/AGENTS.md", "infrastructure/AGENTS.md"):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())

    def test_shared_design_tokens_exist(self):
        tokens = (ROOT / "packages/design-system/src/tokens/tokens.css").read_text(encoding="utf-8")
        for token in ("--color-text:", "--color-background:", "--font-family-body:", "--space-4:"):
            with self.subTest(token=token):
                self.assertIn(token, tokens)


if __name__ == "__main__":
    unittest.main()
