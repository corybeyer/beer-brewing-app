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
    tags = {name: project + ':' + name for name in
            ('app', 'operator', 'smoke', 'broken', 'baseline-app', 'baseline-operator')}
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
            # Fixtures reproduce the baseline's exact readiness/migration contract.
            # They do not claim to be a previously published image or new feature API.
            deployment.command('build', '-t', tags['baseline-app'], '-', input=(
                f'FROM {tags["app"]}\nUSER root\n'
                'RUN python -c "from pathlib import Path; import brewery_database.connection as c; '
                'p=Path(c.__file__); p.write_text(p.read_text().replace(\'0002_recipe_drafts\', \'0001_baseline\'))"\n'
                'USER brewery\n').encode())
            deployment.command('build', '-t', tags['baseline-operator'], '-', input=(
                f'FROM {tags["operator"]}\nUSER root\n'
                'RUN rm /srv/brewery/packages/database/migrations/versions/0002_recipe_drafts.py\n'
                'USER brewery\n').encode())
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
            print('RUN: adopt baseline UI/API, then reject a broken recipe candidate after migration', flush=True)
            deployment.deploy_images(tags['baseline-app'], tags['baseline-operator'])
            assert deployment.revision() == '0001_baseline'
            deployment.sql("CREATE TABLE rollout_fixture (note text NOT NULL); "
                           "INSERT INTO rollout_fixture VALUES ('retained through rollout and restore')")
            try:
                deployment.deploy_images(tags['broken'], tags['operator'])
            except subprocess.CalledProcessError:
                pass
            else:
                raise RuntimeError('Broken upgrade candidate unexpectedly deployed')
            assert deployment.revision() == '0002_recipe_drafts'
            assert not (root / 'state.json').exists()
            with urlopen('http://127.0.0.1:' + port + '/health', timeout=5) as response:
                assert response.status == 200
            try:
                urlopen('http://127.0.0.1:' + port + '/', timeout=5)
            except HTTPError as response:
                assert response.code == 404
            else:
                raise RuntimeError('Incompatible baseline API was not replaced by retained smoke service')
            print('RUN: re-adopt recipe UI/API with retained data and populate a runtime-owned draft', flush=True)
            deployment.deploy_images(tags['app'], tags['operator'])
            application = json.loads(deployment.command('inspect', deployment.compose('ps', '-q', 'brewery').decode().strip()))[0]
            mounts = [mount for mount in application['Mounts'] if mount['Destination'].startswith('/run/secrets/')]
            assert application['Config']['User'] == 'brewery'
            assert len(mounts) == 1 and mounts[0]['Destination'] == '/run/secrets/app-password' and not mounts[0]['RW']
            database = json.loads(deployment.command('inspect', deployment.compose('ps', '-q', 'database').decode().strip()))[0]
            assert not database['NetworkSettings']['Ports'].get('5432/tcp')
            deployment.compose('exec', '-T', 'brewery', 'python', '-c',
                               'from brewery_config import database_url; '
                               'from brewery_database.connection import create_database_engine; '
                               'from brewery_database.recipes import PostgresRecipeDraftStore; '
                               'from brewery_domain.recipes import RecipeDraft; '
                               'from brewery_domain.recipe_plan import RecipePlan, Ingredient; '
                               'engine=create_database_engine(database_url()); '
                               'PostgresRecipeDraftStore(engine).create(RecipeDraft("rollout-recipe",1,'
                               'RecipePlan("rollout-version",(Ingredient("yeast","rollout-version"),)),"Retained draft")); '
                               'engine.dispose()')
            backup = deployment.backup()
            assert json.loads((backup / 'metadata.json').read_text())['verified'] is True
            assert json.loads((backup / 'metadata.json').read_text())['consistency'] == 'exported-snapshot'
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
            print('RUN: reject recipe-to-baseline downgrade without changing production', flush=True)
            try:
                deployment.deploy_images(tags['baseline-app'], tags['baseline-operator'])
            except ValueError:
                pass
            else:
                raise RuntimeError('Reverse schema transition unexpectedly accepted')
            deployment.validate_service('brewery')
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
            assert deployment.sql("SELECT name FROM recipe_version WHERE id = 'rollout-version'") == 'Retained draft'
            assert not deployment.sql("SELECT datname FROM pg_database WHERE datname LIKE 'brew_verify_%'", 'postgres')
            print('PASS: baseline-to-recipe migration, populated snapshot restore, incompatible/compatible recovery, '
                  'reverse-transition rejection, and retained-data re-adoption', flush=True)
        finally:
            try:
                deployment.compose('down', '--volumes', '--remove-orphans')
            finally:
                for name in ('baseline-app', 'baseline-operator', 'broken', 'app', 'operator', 'smoke'):
                    subprocess.run(['/usr/bin/docker', 'image', 'rm', tags[name]], capture_output=True, check=False)


if __name__ == '__main__':
    main()
