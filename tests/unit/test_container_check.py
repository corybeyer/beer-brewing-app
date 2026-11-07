"""Protect development data when the disposable container check fails."""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from scripts.development import check_containers


class ContainerCheckSafetyTests(unittest.TestCase):
    def test_unavailable_daemon_does_not_attempt_cleanup_or_create_resources(self):
        with patch.object(check_containers, 'run', side_effect=subprocess.CalledProcessError(1, 'docker')):
            with patch.object(check_containers.tempfile, 'TemporaryDirectory') as temporary:
                with patch.object(check_containers.subprocess, 'run') as cleanup:
                    with self.assertRaises(subprocess.CalledProcessError):
                        check_containers.main()
        temporary.assert_not_called()
        cleanup.assert_not_called()

    def test_startup_failure_cleans_only_isolated_project_resources(self):
        self.assert_startup_failure(False)

    def test_candidate_only_changes_runtime_image_and_keeps_isolated_cleanup(self):
        self.assert_startup_failure(True)

    def assert_startup_failure(self, candidate):
        observed = {}

        def command(*arguments, **options):
            if arguments[:2] == ('docker', 'info'):
                return 'aarch64'
            if 'config' in arguments:
                secret_directory = Path(options['env']['BREWERY_SECRETS_DIR'])
                observed['directory'] = secret_directory
                return json.dumps({
                    'name': 'brewery-development',
                    'volumes': {'postgres-data': {'name': 'brewery-development_postgres-data'}},
                    'networks': {'default': {'name': 'brewery-development_default'}},
                    'secrets': {name: {'file': str(secret_directory / name)}
                                for name in ('admin-password', 'migrator-password', 'app-password')},
                    'services': {
                        name: {'ports': [{'published': '8081', 'target': 8081}],
                               'build': {'dockerfile': 'infrastructure/docker/api.Dockerfile'}}
                        for name in ('backend', 'provision', 'migrate')
                    },
                })
            if 'up' in arguments:
                config_path = Path(arguments[arguments.index('-f') + 1])
                config = json.loads(config_path.read_text())
                project = arguments[arguments.index('-p') + 1]
                self.assertTrue(project.startswith('brewery-check-'))
                self.assertNotIn('brewery-development', json.dumps(config))
                self.assertEqual(config['name'], project)
                for resource in (config['volumes']['postgres-data'], config['networks']['default']):
                    self.assertTrue(resource['name'].startswith(project + '-'))
                self.assertEqual(config['services']['backend']['ports'][0]['host_ip'], '127.0.0.1')
                self.assertEqual(config['services']['backend']['ports'][0]['published'], '0')
                self.assertEqual(config['services']['backend']['ports'][0]['target'], 8080 if candidate else 8081)
                self.assertEqual(config['services']['backend']['build']['dockerfile'],
                                 'infrastructure/docker/candidate.Dockerfile' if candidate
                                 else 'infrastructure/docker/api.Dockerfile')
                for name in ('provision', 'migrate'):
                    self.assertEqual(config['services'][name]['build']['dockerfile'],
                                     'infrastructure/docker/api.Dockerfile')
                for secret in config['secrets'].values():
                    self.assertEqual(Path(secret['file']).parent, config_path.parent)
                    self.assertTrue(Path(secret['file']).is_file())
                observed['compose'] = list(arguments[:arguments.index('up')])
                raise subprocess.CalledProcessError(1, arguments)
            self.fail(f'Unexpected command: {arguments}')

        with patch.object(check_containers, 'run', side_effect=command):
            with patch.object(check_containers.subprocess, 'run') as cleanup:
                with self.assertRaises(subprocess.CalledProcessError):
                    check_containers.main(candidate=candidate)
        self.assertFalse(observed['directory'].exists())
        self.assertEqual(cleanup.call_args_list[0].args[0],
                         [*observed['compose'], 'down', '--volumes', '--remove-orphans'])
        project = observed['compose'][3]
        self.assertEqual(cleanup.call_args_list[1].args[0], ['docker', 'rm', '-f', project + '-smoke'])
        self.assertEqual(cleanup.call_args_list[2].args[0], ['docker', 'image', 'rm', project + ':smoke'])
