"""Deployment failure paths must retain data and restore application configuration."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from infrastructure.deployment.production import install
from infrastructure.deployment.production.install import install_files, refuse_unclaimed_volume
from infrastructure.deployment.production.rollout import Deployment, REPOSITORY


class ProductionRolloutTests(unittest.TestCase):
    @contextmanager
    def snapshot(self):
        yield Mock(sql=Mock(return_value='00000003-0000001B-1'))

    def test_failed_restore_never_publishes_backup_or_prunes_existing_sets(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            deployment = Deployment(root, root / 'backups')
            deployment.backups.mkdir(mode=0o700)
            retained = deployment.backups / 'unrelated-private-file'
            retained.write_text('keep')

            def compose(*args, **kwargs):
                if 'pg_restore' in args:
                    raise RuntimeError('simulated restore failure')
                return b'custom-dump'

            with patch.object(deployment, 'revision', return_value='0001_baseline'):
                with patch.object(deployment, 'table_fingerprints', return_value=['fixture|1|digest']):
                    with patch.object(deployment, 'compose', side_effect=compose):
                        with patch.object(deployment, 'sql') as sql:
                            with patch.object(deployment, 'snapshot', self.snapshot):
                                with self.assertRaisesRegex(RuntimeError, 'restore failure'):
                                    deployment.backup()
            self.assertEqual(list(deployment.backups.iterdir()), [retained])
            self.assertTrue(sql.call_args_list[-1].args[0].startswith('DROP DATABASE brew_verify_'))
            self.assertTrue(all('DROP DATABASE brewery' not in call.args[0] for call in sql.call_args_list))

    def test_restored_contents_must_match_before_credentials_are_copied(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            deployment = Deployment(root, root / 'backups')
            with patch.object(deployment, 'revision', return_value='0001_baseline'):
                with patch.object(deployment, 'table_fingerprints', side_effect=[['fixture|1|a'], ['fixture|1|b']]):
                    with patch.object(deployment, 'compose', return_value=b'dump'):
                        with patch.object(deployment, 'sql'):
                            with patch.object(deployment, 'snapshot', self.snapshot):
                                with self.assertRaisesRegex(ValueError, 'contents'):
                                    deployment.backup()
            self.assertEqual(list(deployment.backups.iterdir()), [])

    def test_commit_validation_rejects_arguments_before_docker_access(self):
        deployment = Deployment('/unused', '/unused')
        with patch.object(deployment, 'command') as command:
            for commit in ('main', '--help', 'a' * 39, 'A' * 40, 'a' * 40 + '\n', 'abc;other'):
                with self.assertRaises(ValueError):
                    deployment.image(commit, 'app')
            command.assert_not_called()

    def test_invalid_exported_snapshot_is_rejected_before_dump(self):
        with TemporaryDirectory() as directory:
            deployment = Deployment(Path(directory), Path(directory) / 'backups')
            with patch.object(deployment, 'compose') as compose:
                with patch.object(deployment, 'snapshot') as snapshot:
                    snapshot.return_value.__enter__.return_value.sql.return_value = 'invalid snapshot'
                    with self.assertRaisesRegex(ValueError, 'snapshot identifier'):
                        deployment.backup()
            compose.assert_not_called()

    def test_image_requires_matching_commit_label_and_registry_digest(self):
        deployment = Deployment('/unused', '/unused')
        commit = 'a' * 40
        reference = REPOSITORY + '@sha256:' + 'b' * 64
        for label, digest, accepted in [(commit, reference, True), ('c' * 40, reference, False),
                                        (commit, 'other.example/image@sha256:' + 'b' * 64, False)]:
            payload = [{'Config': {'Labels': {'org.opencontainers.image.revision': label}}, 'RepoDigests': [digest]}]
            with patch.object(deployment, 'command', side_effect=[b'', json.dumps(payload).encode()]):
                if accepted:
                    self.assertEqual(deployment.image(commit, 'app'), reference)
                else:
                    with self.assertRaises(ValueError):
                        deployment.image(commit, 'app')

    def test_failed_candidate_never_switches_production_and_restores_environment(self):
        self.check_failure('candidate', prior=False)

    def test_failed_live_service_restores_previous_image_without_database_downgrade(self):
        self.check_failure('brewery', prior=True)

    def test_failed_first_live_service_restores_legacy_service(self):
        self.check_failure('brewery', prior=False)

    def check_failure(self, failing, prior):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('previous-private-configuration')
            if prior:
                (root / 'state.json').write_text(json.dumps({'application': 'old-app', 'operator': 'old-operator'}))
            deployment = Deployment(root, root / 'backups')
            calls = []

            def validate(service):
                calls.append(service)
                if service == failing and calls.count(service) == 1:
                    raise RuntimeError('simulated failed HTTP check')

            with patch.object(deployment, 'command', return_value=b'0001_baseline\n'):
                with patch.object(deployment, 'compose', return_value=b'') as compose:
                    with patch.object(deployment, 'revision', return_value='0001_baseline'):
                        with patch.object(deployment, 'backup') as backup:
                            with patch.object(deployment, 'validate_service', side_effect=validate):
                                with patch.object(deployment, 'legacy_rollback') as legacy:
                                    with self.assertRaisesRegex(RuntimeError, 'simulated'):
                                        deployment.deploy_images('new-app', 'new-operator')
            self.assertEqual((root / '.env').read_text(), 'previous-private-configuration')
            backup.assert_called_once()
            self.assertEqual(legacy.call_count, int(failing == 'brewery' and not prior))
            production_calls = [call for call in compose.call_args_list if 'up' in call.args and call.args[-1] == 'brewery']
            self.assertEqual(len(production_calls), 0 if failing == 'candidate' else (2 if prior else 1))
            all_arguments = repr(compose.call_args_list)
            self.assertNotIn('downgrade', all_arguments)
            self.assertNotIn('--volumes', all_arguments)
            self.assertIn("('rm', '-s', '-f', 'candidate')", all_arguments)

    def test_future_migration_is_rejected_before_database_changes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('prior')
            deployment = Deployment(root, root / 'backups')
            with patch.object(deployment, 'command', return_value=b'0002_future'):
                with patch.object(deployment, 'compose') as compose:
                    with self.assertRaisesRegex(ValueError, 'reviewed schema pair'):
                        deployment.deploy_images('app', 'operator')
            self.assertEqual((root / '.env').read_text(), 'prior')
            compose.assert_called_once_with('rm', '-s', '-f', 'candidate')


class ProductionInstallerTests(unittest.TestCase):
    def test_privileged_preflight_uses_root_docker_configuration(self):
        with TemporaryDirectory() as directory:
            deployment = Mock()
            deployment.root = Path(directory) / 'not-installed'
            deployment.command.return_value = b''
            current = {'name': 'beer-brewing-app', 'services': {'brewery': {
                'image': REPOSITORY + '@sha256:' + 'b' * 64,
                'ports': [{'target': 8080, 'published': '8080', 'protocol': 'tcp'}],
            }}}
            with (
                patch.object(install.argparse.ArgumentParser, 'parse_args', return_value=argparse.Namespace(commit='a' * 40)),
                patch.object(install.os, 'geteuid', return_value=0),
                patch.object(install.os, 'umask'),
                patch.object(install.subprocess, 'check_output', return_value=json.dumps(current).encode()) as inspect,
                patch.object(install, 'Deployment', return_value=deployment),
                patch.object(install, 'private_directory'),
                patch.object(install, 'install_files', side_effect=RuntimeError('stop before installing')),
            ):
                with self.assertRaisesRegex(RuntimeError, 'stop before installing'):
                    install.main()
            self.assertEqual(inspect.call_args.kwargs['env'], {'PATH': '/usr/bin:/bin', 'HOME': '/root'})

    def test_first_install_refuses_an_unclaimed_existing_production_volume(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / 'not-installed'
            deployment = Deployment(root, root / 'backups')
            with patch.object(deployment, 'command', return_value=b'brewery-production-postgres\n'):
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    refuse_unclaimed_volume(deployment)
            self.assertFalse(root.exists())
            with patch.object(deployment, 'command', return_value=b'unrelated-volume\n'):
                refuse_unclaimed_volume(deployment)
            self.assertFalse(root.exists())

    def test_installer_retains_exact_legacy_files_and_creates_private_credentials(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host, binaries, units = [root / name for name in ('host', 'bin', 'units')]
            for path in (host, binaries, units):
                path.mkdir(mode=0o700)
            (host / 'compose.yaml').write_text('legacy-compose')
            (host / '.env').write_text('legacy-private-environment')
            (binaries / 'brewery-deploy').write_text('legacy-deployer')
            for path in (host / 'compose.yaml', host / '.env', binaries / 'brewery-deploy'):
                path.chmod(0o600)
            runtime = install_files(host, binaries, units, ('legacy-image', 'operator-image'))
            self.assertEqual((host / 'compose.yaml').read_text(), 'legacy-compose')
            self.assertEqual((host / '.env').read_text(), 'legacy-private-environment')
            self.assertEqual((runtime / 'legacy-deploy').read_text(), 'legacy-deployer')
            self.assertEqual((runtime / 'legacy.env').read_text(), 'legacy-private-environment')
            self.assertEqual((runtime / 'legacy-compose.yaml').read_text(), 'legacy-compose')
            self.assertIn('python3 -I', (binaries / 'brewery-deploy').read_text())
            self.assertEqual((binaries / 'brewery-deploy').stat().st_mode & 0o777, 0o700)
            self.assertEqual(runtime.stat().st_mode & 0o777, 0o700)
            self.assertEqual((runtime / '.env').stat().st_mode & 0o777, 0o600)
            credentials = list((runtime / 'secrets').iterdir())
            self.assertEqual(len({path.read_text() for path in credentials}), 3)
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o444 for path in credentials))
            before = [path.read_bytes() for path in credentials]
            with self.assertRaisesRegex(ValueError, 'already staged'):
                install_files(host, binaries, units, ('other-image', 'other-operator'))
            self.assertEqual([path.read_bytes() for path in credentials], before)

    def test_installer_refuses_foreign_commands_before_changing_legacy_deployer(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            host, binaries, units = [root / name for name in ('host', 'bin', 'units')]
            for path in (host, binaries, units):
                path.mkdir(mode=0o700)
            for path in (host / 'compose.yaml', host / '.env', binaries / 'brewery-deploy'):
                path.write_text('original')
                path.chmod(0o600)
            (binaries / 'brewery-backup').write_text('unrelated administrator command')
            with self.assertRaisesRegex(ValueError, 'unrelated'):
                install_files(host, binaries, units, ('app', 'operator'))
            self.assertEqual((binaries / 'brewery-deploy').read_text(), 'original')
            self.assertFalse((host / 'runtime').exists())
