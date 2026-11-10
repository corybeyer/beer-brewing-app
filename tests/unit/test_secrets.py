"""Local secret creation preserves credentials and restricts the parent directory."""

from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest

from scripts.development.create_secrets import create_secrets


class SecretFileTests(unittest.TestCase):
    def test_passwords_are_distinct_and_preserved_on_repeat(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            create_secrets(root)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            self.assertEqual(len(before), 3)
            self.assertEqual(len(set(before.values())), 3)
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o444 for p in root.iterdir()))
            create_secrets(root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_open_directory_and_symlink_secret_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "secrets"
            root.mkdir(mode=0o755)
            # Establish the invalid fixture independently of the caller's umask.
            root.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "0700"):
                create_secrets(root)
            root.chmod(0o700)
            (root / "admin-password").symlink_to(Path(directory) / "missing")
            with self.assertRaisesRegex(ValueError, "regular file"):
                create_secrets(root)
