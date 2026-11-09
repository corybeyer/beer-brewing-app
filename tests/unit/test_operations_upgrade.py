"""Explicit operations upgrades preserve host state and refuse unknown installs."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from infrastructure.deployment.production import upgrade
from infrastructure.deployment.production.install import install_files
from infrastructure.deployment.production.rollout import Deployment


SOURCE = Path(__file__).resolve().parents[2] / 'infrastructure/deployment/production'


class OperationsUpgradeTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.host, self.binaries, self.units = [self.root / name for name in ('host', 'bin', 'units')]
        for path in (self.host, self.binaries, self.units):
            path.mkdir(mode=0o700)
        for path in (self.host / 'compose.yaml', self.host / '.env', self.binaries / 'brewery-deploy'):
            path.write_text('retained legacy content')
            path.chmod(0o600)
        self.runtime = install_files(self.host, self.binaries, self.units, ('old-app', 'old-operator'))
        (self.runtime / 'state.json').write_text(json.dumps({'application': 'old-app', 'operator': 'old-operator'}))
        (self.runtime / 'state.json').chmod(0o600)

    def update(self):
        return upgrade.upgrade_operations(self.host, self.binaries, SOURCE, 'a' * 40)

    def preserved(self):
        paths = [*(self.host.glob('*')), self.host / '.env', *self.binaries.iterdir(), *self.units.iterdir(),
                 *(self.runtime / 'secrets').iterdir(), self.runtime / '.env', self.runtime / 'state.json',
                 self.runtime / 'installation.json', self.runtime / 'compose.yaml',
                 self.runtime / 'legacy.env', self.runtime / 'legacy-compose.yaml', self.runtime / 'legacy-deploy']
        return {str(path): (path.read_bytes(), path.stat().st_mode & 0o777) for path in paths if path.is_file()}

    def test_known_predecessor_upgrade_retains_state_and_is_idempotent(self):
        original = '# fixture for a reviewed installed predecessor\n'
        (self.runtime / 'rollout.py').write_text(original)
        digest = hashlib.sha256(original.encode()).hexdigest()
        before = self.preserved()
        with patch.object(upgrade, 'PREDECESSOR_SHA256', digest):
            result = self.update()
        self.assertEqual(self.preserved(), before)
        self.assertEqual((self.runtime / 'operations-history' / f'rollout-{digest}.py').read_text(), original)
        self.assertEqual(result, hashlib.sha256((SOURCE / 'rollout.py').read_bytes()).hexdigest())
        self.assertEqual(self.update(), result)
        self.assertEqual(self.preserved(), before)
        self.assertEqual((self.runtime / 'rollout.py').stat().st_mode & 0o777, 0o600)

    def test_unknown_predecessor_foreign_launcher_or_compose_is_refused(self):
        for path in (self.runtime / 'rollout.py', self.binaries / 'brewery-backup', self.runtime / 'compose.yaml'):
            original = path.read_bytes()
            path.write_text('unrelated administrator content')
            before = self.preserved()
            with self.assertRaises(ValueError):
                self.update()
            self.assertEqual(self.preserved(), before)
            path.write_bytes(original)

    def test_symlinks_and_changed_legacy_identity_are_refused(self):
        target = self.runtime / 'legacy.env'
        original = target.read_bytes()
        target.unlink()
        target.symlink_to(self.host / '.env')
        with self.assertRaises(ValueError):
            self.update()
        target.unlink()
        target.write_bytes(original + b'changed')
        target.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'legacy installation'):
            self.update()

    def test_receipt_failure_restores_original_script(self):
        original = '# fixture for known predecessor\n'
        (self.runtime / 'rollout.py').write_text(original)
        digest = hashlib.sha256(original.encode()).hexdigest()
        write = upgrade.atomic_write

        def fail_receipt(path, content, **options):
            if path.name == 'operations.json':
                raise OSError('simulated receipt failure')
            return write(path, content, **options)

        with patch.object(upgrade, 'PREDECESSOR_SHA256', digest):
            with patch.object(upgrade, 'atomic_write', side_effect=fail_receipt):
                with self.assertRaises(OSError):
                    self.update()
        self.assertEqual((self.runtime / 'rollout.py').read_text(), original)

    def test_active_operation_lock_prevents_replacement(self):
        original = (self.runtime / 'rollout.py').read_bytes()
        with Deployment(self.runtime, self.root / 'backups').locked():
            with self.assertRaises(BlockingIOError):
                self.update()
        self.assertEqual((self.runtime / 'rollout.py').read_bytes(), original)

    def test_symlinked_operation_lock_is_never_followed(self):
        unrelated = self.root / 'unrelated'
        unrelated.write_text('keep')
        (self.runtime / 'operation.lock').symlink_to(unrelated)
        with self.assertRaises(OSError):
            self.update()
        self.assertEqual(unrelated.read_text(), 'keep')

    def test_reviewed_checkout_must_match_and_be_clean(self):
        for outputs in (['b' * 40 + '\n'], ['a' * 40 + '\n', ' M modified.py\n']):
            with patch.object(upgrade.subprocess, 'check_output', side_effect=outputs):
                with self.assertRaises(ValueError):
                    upgrade.verify_checkout(SOURCE, 'a' * 40)
        with patch.object(upgrade.subprocess, 'check_output', side_effect=['a' * 40 + '\n', '']):
            upgrade.verify_checkout(SOURCE, 'a' * 40)
        with patch.object(upgrade.subprocess, 'check_output') as command:
            with self.assertRaises(ValueError):
                upgrade.verify_checkout(SOURCE, '--help')
            command.assert_not_called()


    def test_known_recipe_operations_predecessor_preserves_installed_state(self):
        original = '# fixture for the reviewed recipe-schema deployer\n'
        (self.runtime / 'rollout.py').write_text(original)
        digest = hashlib.sha256(original.encode()).hexdigest()
        before = self.preserved()
        with patch.object(upgrade, 'RECIPE_PREDECESSOR_SHA256', digest):
            self.update()
        self.assertEqual(self.preserved(), before)
        self.assertEqual((self.runtime / 'operations-history' / f'rollout-{digest}.py').read_text(), original)


    def test_known_catalogue_operations_predecessor_preserves_installed_state(self):
        original = '# fixture for the reviewed catalogue-schema deployer\n'
        (self.runtime / 'rollout.py').write_text(original)
        digest = hashlib.sha256(original.encode()).hexdigest()
        before = self.preserved()
        with patch.object(upgrade, 'CATALOGUE_PREDECESSOR_SHA256', digest):
            self.update()
        self.assertEqual(self.preserved(), before)
        self.assertEqual((self.runtime / 'operations-history' / f'rollout-{digest}.py').read_text(), original)
