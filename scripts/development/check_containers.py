"""Exercise M1 containers in an isolated, disposable Compose project.

Requires Docker Compose v2 and daemon access. Never uses the default project,
saved credentials, production configuration, or a published database port.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import uuid


ROOT = Path(__file__).resolve().parents[2]


def run(*command, env=None, timeout=600):
    return subprocess.check_output(command, cwd=ROOT, env=env, text=True, timeout=timeout).strip()


def wait_json(url, status, payload, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            try:
                response = urlopen(url, timeout=5)
            except HTTPError as error:
                response = error
            with response:
                if response.status == status and json.load(response) == payload:
                    return
        except (OSError, URLError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError(f'Timed out waiting for HTTP {status} at {url}')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main(candidate=False):
    # Fail before creating resources if Docker is unavailable.
    run('docker', 'info', '--format', '{{.Architecture}}')
    project = 'brewery-check-' + uuid.uuid4().hex[:12]
    smoke = project + '-smoke'
    smoke_image = project + ':smoke'
    backend_port = '8080' if candidate else '8081'
    with tempfile.TemporaryDirectory(prefix='brewery-container-check-') as directory:
        private = Path(directory)
        for name in ('admin-password', 'migrator-password', 'app-password'):
            path = private / name
            path.write_text(secrets.token_hex(32) + '\n')
            path.chmod(0o444)  # Private 0700 parent; readable assigned container mount.
        environment = dict(os.environ, BREWERY_SECRETS_DIR=directory)
        config = json.loads(run('docker', 'compose', '-f', str(ROOT / 'compose.yaml'),
                                'config', '--format', 'json', env=environment))
        config['name'] = project
        # `compose config` expands generated resource names using the original
        # project. Rebind them so this test cannot touch a developer's volume.
        config['volumes']['postgres-data']['name'] = project + '-postgres-data'
        config['networks']['default']['name'] = project + '-default'
        # Docker assigns a free loopback port, avoiding a developer's running API.
        config['services']['backend']['ports'] = [
            {'target': int(backend_port), 'published': '0', 'host_ip': '127.0.0.1', 'protocol': 'tcp'}
        ]
        if candidate:
            config['services']['backend']['build']['dockerfile'] = 'infrastructure/docker/candidate.Dockerfile'
        config_path = private / 'compose.json'
        config_path.write_text(json.dumps(config))
        compose = ['docker', 'compose', '-p', project, '-f', str(config_path)]

        def dc(*arguments):
            return run(*compose, *arguments, env=environment)

        def backend_url():
            return 'http://' + dc('port', 'backend', backend_port)

        def browser_check(phase, readiness):
            if candidate:
                subprocess.run(['npm', 'exec', '--', 'playwright', 'test', '--config',
                                'apps/web/playwright.serving.config.ts'], cwd=ROOT,
                               env=dict(environment, BREWERY_SERVING_BASE_URL=backend_url(),
                                        BREWERY_SERVING_PHASE=phase, BREWERY_SERVING_READINESS=readiness),
                               check=True, timeout=180)

        def inspect_backend():
            return json.loads(run('docker', 'inspect', dc('ps', '-q', 'backend')))[0]

        def database_identity():
            return dc('exec', '-T', 'database', 'psql', '-U', 'brewery_admin', '-d',
                      'brewery', '-Atc', 'SELECT system_identifier FROM pg_control_system()')

        try:
            print('RUN: build and start isolated development stack', flush=True)
            dc('up', '--build', '-d', '--wait', '--wait-timeout', '120')
            url = backend_url()
            wait_json(url + '/health', 200, {'status': 'ok', 'service': 'beer-brewing-app'})
            wait_json(url + '/api/v1/readiness', 200, {'status': 'ready'})
            backend = inspect_backend()
            require(backend['Config']['User'] == 'brewery', 'API must run as brewery')
            secret_mounts = {mount['Destination']: mount for mount in backend['Mounts']
                             if mount['Destination'].startswith('/run/secrets/')}
            require(set(secret_mounts) == {'/run/secrets/app-password'},
                    'API received unexpected secret mounts')
            require(not secret_mounts['/run/secrets/app-password']['RW'],
                    'API secret must be read-only')
            database = json.loads(run('docker', 'inspect', dc('ps', '-q', 'database')))[0]
            require(not database['NetworkSettings']['Ports'].get('5432/tcp'),
                    'Database port must remain private')
            identity = database_identity()
            require(bool(identity), 'Database identity must be available')
            browser_check('startup', 'ready')

            print('RUN: database outage preserves liveness and fails readiness', flush=True)
            dc('stop', 'database')
            wait_json(url + '/health', 200, {'status': 'ok', 'service': 'beer-brewing-app'})
            wait_json(url + '/api/v1/readiness', 503, {'status': 'unavailable'})
            browser_check('outage', 'unavailable')
            dc('start', 'database')
            wait_json(url + '/api/v1/readiness', 200, {'status': 'ready'})
            browser_check('recovery', 'ready')

            print('RUN: recreate containers and retain the initialized database', flush=True)
            dc('down')
            dc('up', '-d', '--wait', '--wait-timeout', '120')
            require(database_identity() == identity, 'Database volume was replaced')
            wait_json(backend_url() + '/api/v1/readiness', 200, {'status': 'ready'})

            print('RUN: retained production smoke image', flush=True)
            run('docker', 'build', '-t', smoke_image, '.')
            run('docker', 'run', '-d', '--name', smoke, '-p', '127.0.0.1::8080', smoke_image)
            smoke_url = 'http://' + run('docker', 'port', smoke, '8080/tcp')
            wait_json(smoke_url + '/health', 200, {'status': 'ok', 'service': 'beer-brewing-app'})
            smoke_state = json.loads(run('docker', 'inspect', smoke))[0]
            require(smoke_state['Config']['User'] == 'appuser', 'Smoke must remain non-root')
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if run('docker', 'inspect', '--format', '{{.State.Health.Status}}', smoke) == 'healthy':
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Smoke Docker health check did not become healthy')
            print('PASS: M1 container startup, secret isolation, outage, persistence, smoke health', flush=True)
        finally:
            # Only resources named by this invocation are removed, including its test volume.
            # Do not print environment/configuration or application logs containing credentials.
            subprocess.run([*compose, 'down', '--volumes', '--remove-orphans'],
                           cwd=ROOT, env=environment, check=False, timeout=120)
            subprocess.run(['docker', 'rm', '-f', smoke], check=False, capture_output=True, timeout=30)
            subprocess.run(['docker', 'image', 'rm', smoke_image], check=False, capture_output=True, timeout=30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', action='store_true', help='Test the built UI/API candidate on port 8080 with live browser checks')
    main(candidate=parser.parse_args().candidate)
