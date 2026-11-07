"""Exercise production rollout/restore/rollback with disposable local Docker resources."""
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.request import urlopen
import uuid

from infrastructure.deployment.production.rollout import Deployment


ROOT = Path(__file__).resolve().parents[2]


def main():
    subprocess.run(['/usr/bin/docker', 'info', '--format', '{{.Architecture}}'],
                   check=True, capture_output=True)
    project = 'brewery-rollout-' + uuid.uuid4().hex[:12]
    tags = {name: project + ':' + name for name in ('app', 'operator', 'smoke', 'broken')}
    with tempfile.TemporaryDirectory(prefix='brewery-rollout-') as directory:
        root = Path(directory)
        (root / 'secrets').mkdir(mode=0o700)
        for name in ('admin-password', 'migrator-password', 'app-password'):
            (root / 'secrets' / name).write_text(secrets.token_hex(32) + '\n')
            (root / 'secrets' / name).chmod(0o444)
        deployment = Deployment(root, root / 'backups', {
            'BREWERY_PROJECT_NAME': project, 'BREWERY_DATA_VOLUME': project + '-data',
            'BREWERY_BIND_ADDRESS': '127.0.0.1', 'BREWERY_HTTP_PORT': '0',
        })
        shutil.copyfile(ROOT / 'infrastructure/deployment/production/compose.yaml', root / 'compose.yaml')
        deployment.write_environment(tags['smoke'], tags['operator'])
        try:
            for name, dockerfile in [('smoke', 'Dockerfile'), ('operator', 'infrastructure/docker/api.Dockerfile'),
                                     ('app', 'infrastructure/docker/candidate.Dockerfile')]:
                print('RUN: build rollout test image ' + name, flush=True)
                deployment.command('build', '-f', dockerfile, '-t', tags[name], str(ROOT))
            deployment.command('build', '-t', tags['broken'], '-', input=(
                f'FROM {tags["app"]}\nENV WEB_ASSETS_DIRECTORY=/nonexistent\n').encode())
            (root / 'legacy.env').write_text('')
            legacy = {'name': project, 'services': {'brewery': {
                'image': tags['smoke'], 'ports': ['127.0.0.1::8080'],
            }}}
            (root / 'legacy-compose.yaml').write_text(json.dumps(legacy))
            deployment.legacy_rollback()
            address = deployment.command('compose', '-p', project, '-f', str(root / 'legacy-compose.yaml'),
                                         'port', 'brewery', '8080').decode().strip()
            port = address.rsplit(':', 1)[1]
            legacy['services']['brewery']['ports'] = [f'127.0.0.1:{port}:8080']
            (root / 'legacy-compose.yaml').write_text(json.dumps(legacy))
            deployment.settings['BREWERY_HTTP_PORT'] = port
            print('RUN: adopt UI/API with verified pre-migration backup', flush=True)
            deployment.deploy_images(tags['app'], tags['operator'])
            application = json.loads(deployment.command('inspect', deployment.compose('ps', '-q', 'brewery').decode().strip()))[0]
            mounts = [mount for mount in application['Mounts'] if mount['Destination'].startswith('/run/secrets/')]
            assert application['Config']['User'] == 'brewery'
            assert len(mounts) == 1 and mounts[0]['Destination'] == '/run/secrets/app-password' and not mounts[0]['RW']
            database = json.loads(deployment.command('inspect', deployment.compose('ps', '-q', 'database').decode().strip()))[0]
            assert not database['NetworkSettings']['Ports'].get('5432/tcp')
            deployment.sql("CREATE TABLE rollout_fixture (note text NOT NULL); "
                           "INSERT INTO rollout_fixture VALUES ('retained through rollout and restore')")
            backup = deployment.backup()
            assert json.loads((backup / 'metadata.json').read_text())['verified'] is True
            assert all((backup / 'credentials' / name).read_bytes() == (root / 'secrets' / name).read_bytes()
                       for name in ('admin-password', 'migrator-password', 'app-password'))
            print('RUN: reject failed candidate while production and data remain ready', flush=True)
            try:
                deployment.deploy_images(tags['broken'], tags['operator'])
            except subprocess.CalledProcessError:
                pass
            else:
                raise RuntimeError('Broken candidate unexpectedly deployed')
            deployment.validate_service('brewery')
            assert deployment.sql('SELECT note FROM rollout_fixture') == 'retained through rollout and restore'
            print('RUN: restore legacy application, then redeploy UI/API with retained data', flush=True)
            deployment.legacy_rollback()
            with urlopen('http://127.0.0.1:' + port + '/health', timeout=5) as response:
                assert response.status == 200
            try:
                urlopen('http://127.0.0.1:' + port + '/', timeout=5)
            except HTTPError as response:
                assert response.code == 404
            else:
                raise RuntimeError('Legacy application did not replace the UI')
            deployment.deploy_images(tags['app'], tags['operator'])
            assert deployment.sql('SELECT note FROM rollout_fixture') == 'retained through rollout and restore'
            assert not deployment.sql("SELECT datname FROM pg_database WHERE datname LIKE 'brew_verify_%'", 'postgres')
            print('PASS: real production adoption, verified populated restore, candidate rejection, and retained-data rollback', flush=True)
        finally:
            try:
                deployment.compose('down', '--volumes', '--remove-orphans')
            finally:
                for name in ('broken', 'app', 'operator', 'smoke'):
                    subprocess.run(['/usr/bin/docker', 'image', 'rm', tags[name]], capture_output=True, check=False)


if __name__ == '__main__':
    main()
