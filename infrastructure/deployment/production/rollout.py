"""Root-installed deployment/backup operations; no application-runtime imports."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
import pwd
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
import uuid


REPOSITORY = 'ghcr.io/corybeyer/beer-brewing-app'
BASELINE = '0001_baseline'


def atomic_write(path, content, mode=0o600):
    with tempfile.NamedTemporaryFile(dir=path.parent, mode='w', delete=False) as output:
        os.chmod(output.name, mode)
        output.write(content)
        temporary = Path(output.name)
    temporary.replace(path)


class Deployment:
    def __init__(self, root, backups, settings=None):
        self.root, self.backups = Path(root), Path(backups)
        self.settings = settings or {}

    def command(self, *arguments, input=None):
        # Ignore caller-provided Docker hosts, contexts, proxies, and Compose variables.
        return subprocess.check_output(['/usr/bin/docker', *arguments], input=input,
                                       env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                                            'HOME': pwd.getpwuid(os.geteuid()).pw_dir}, timeout=600)

    def compose(self, *arguments, input=None):
        return self.command('compose', '--env-file', str(self.root / '.env'),
                            '-f', str(self.root / 'compose.yaml'), *arguments, input=input)

    @contextmanager
    def locked(self):
        with (self.root / 'operation.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def image(self, commit, kind):
        if not re.fullmatch('[0-9a-f]{40}', commit):
            raise ValueError('Expected a full lowercase Git commit SHA')
        tag = f'{REPOSITORY}:{kind}-sha-{commit}'
        self.command('pull', tag)
        details = json.loads(self.command('image', 'inspect', tag))[0]
        if details['Config'].get('Labels', {}).get('org.opencontainers.image.revision') != commit:
            raise ValueError('Image commit label does not match the validated commit')
        references = [value for value in details.get('RepoDigests', [])
                      if re.fullmatch(re.escape(REPOSITORY) + '@sha256:[0-9a-f]{64}', value)]
        if len(references) != 1:
            raise ValueError('Expected one immutable repository image digest')
        return references[0]

    def write_environment(self, application, operator):
        values = {
            'BREWERY_IMAGE': application, 'BREWERY_OPERATOR_IMAGE': operator,
            'BREWERY_SECRETS_DIR': str(self.root / 'secrets'),
            'BREWERY_PROJECT_NAME': 'beer-brewing-app',
            'BREWERY_DATA_VOLUME': 'brewery-production-postgres',
            'BREWERY_BIND_ADDRESS': '0.0.0.0', 'BREWERY_HTTP_PORT': '8080',
            **self.settings,
        }
        if any('\n' in str(value) or '\r' in str(value) for value in values.values()):
            raise ValueError('Deployment settings must be single-line values')
        # JSON quoting is valid Compose dotenv double-quoted syntax.
        atomic_write(self.root / '.env', ''.join(f'{key}={json.dumps(str(value))}\n' for key, value in values.items()))

    def sql(self, statement, database='brewery'):
        return self.compose('exec', '-T', 'database', 'psql', '-U', 'brewery_admin', '-d', database,
                            '-v', 'ON_ERROR_STOP=1', '-Atc', statement).decode().strip()

    def revision(self, database='brewery'):
        exists = self.sql("SELECT to_regclass('public.alembic_version') IS NOT NULL", database)
        return self.sql('SELECT version_num FROM public.alembic_version ORDER BY version_num', database) if exists == 't' else ''

    def table_fingerprints(self, database='brewery'):
        # Server formats identifiers; never interpolate table names into SQL ourselves.
        queries = self.sql("SELECT format($query$SELECT %L, count(*), md5(coalesce(string_agg("
                           "md5(row_to_json(r)::text), '' ORDER BY md5(row_to_json(r)::text)), '')) "
                           "FROM %I.%I AS r$query$, schemaname || '.' || tablename, "
                           "schemaname, tablename) FROM pg_tables WHERE schemaname NOT IN "
                           "('pg_catalog', 'information_schema') ORDER BY schemaname, tablename", database)
        return [self.sql(query, database) for query in queries.splitlines()]

    def backup(self):
        self.backups.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (self.backups.is_symlink() or self.backups.stat().st_mode & 0o077
                or self.backups.stat().st_uid != os.geteuid()):
            raise ValueError('Backup directory must be private and must not be a symlink')
        name = 'brewery-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-') + uuid.uuid4().hex
        verify = 'brew_verify_' + uuid.uuid4().hex
        stage = Path(tempfile.mkdtemp(prefix='.pending-', dir=self.backups))
        created = False
        try:
            revision, fingerprints = self.revision(), self.table_fingerprints()
            # No business write APIs exist yet. Future active writes need a snapshot
            # consistency strategy before fingerprint comparison can be retained.
            with (stage / 'database.dump').open('wb') as dump:
                os.chmod(dump.name, 0o600)
                dump.write(self.compose('exec', '-T', 'database', 'pg_dump', '-U', 'brewery_admin',
                                        '-d', 'brewery', '--format=custom'))
            self.sql(f'CREATE DATABASE {verify} TEMPLATE template0', 'postgres')
            created = True
            self.compose('exec', '-T', 'database', 'pg_restore', '-U', 'brewery_admin',
                         '-d', verify, '--clean', '--if-exists', '--exit-on-error', input=(stage / 'database.dump').read_bytes())
            if self.revision(verify) != revision or self.table_fingerprints(verify) != fingerprints:
                raise ValueError('Restored backup does not match source revision and table contents')
            self.sql(f'DROP DATABASE {verify}', 'postgres')
            created = False
            shutil.copytree(self.root / 'secrets', stage / 'credentials', symlinks=False)
            (stage / 'credentials').chmod(0o700)
            for credential in (stage / 'credentials').iterdir():
                credential.chmod(0o600)
            atomic_write(stage / 'metadata.json', json.dumps({'format': 1, 'revision': revision, 'verified': True,
                         'images': json.loads((self.root / 'state.json').read_text())
                         if (self.root / 'state.json').exists() else None}))
            stage.rename(self.backups / name)
            # Retain only known verified sets; never remove unrelated or linked paths.
            sets = sorted(path for path in self.backups.iterdir()
                          if re.fullmatch(r'brewery-\d{8}T\d{12}Z-[0-9a-f]{32}', path.name)
                          and path.is_dir() and not path.is_symlink()
                          and (path / 'metadata.json').is_file()
                          and json.loads((path / 'metadata.json').read_text()).get('verified') is True)
            for expired in sets[:-7]:
                shutil.rmtree(expired)
            print('Verified private database backup completed.', flush=True)
            return self.backups / name
        finally:
            try:
                if created:
                    self.sql(f'DROP DATABASE {verify}', 'postgres')
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

    def wait_http(self, url, path, expected, timeout=90):
        opener = build_opener(ProxyHandler({}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with opener.open(url + path, timeout=5) as response:
                    if response.status == 200:
                        body = response.read()
                        if expected is None or json.loads(body) == expected:
                            return
            except (OSError, HTTPError, ValueError):
                pass
            time.sleep(1)
        raise RuntimeError('Application HTTP validation did not pass')

    def validate_service(self, service):
        address = self.compose('port', service, '8080').decode().strip()
        port = address.rsplit(':', 1)[1]
        url = 'http://127.0.0.1:' + port
        self.wait_http(url, '/health', {'status': 'ok', 'service': 'beer-brewing-app'})
        self.wait_http(url, '/api/v1/readiness', {'status': 'ready'})
        self.wait_http(url, '/', None)

    def legacy_rollback(self):
        self.command('compose', '-p', self.settings.get('BREWERY_PROJECT_NAME', 'beer-brewing-app'),
                     '--env-file', str(self.root / 'legacy.env'), '-f', str(self.root / 'legacy-compose.yaml'),
                     'up', '-d', '--wait', '--wait-timeout', '120', 'brewery')
        (self.root / 'state.json').unlink(missing_ok=True)

    def deploy_images(self, application, operator):
        previous_env = (self.root / '.env').read_text() if (self.root / '.env').exists() else None
        state_path = self.root / 'state.json'
        previous = json.loads(state_path.read_text()) if state_path.exists() else None
        changed = False
        try:
            # Explicitly reject future migration graphs until compatibility is reviewed.
            schema = self.command('run', '--rm', '--network', 'none', '--entrypoint', 'python', application,
                                  '-c', 'from brewery_database.connection import SCHEMA_REVISION; print(SCHEMA_REVISION)').decode().strip()
            heads = self.command('run', '--rm', '--network', 'none', '--entrypoint', 'python', operator,
                                 '-c', 'from alembic.config import Config; from alembic.script import ScriptDirectory; '
                                 'print(",".join(ScriptDirectory.from_config(Config("alembic.ini")).get_heads()))').decode().strip()
            if schema != BASELINE or heads != BASELINE:
                raise ValueError('Deployment supports only the explicitly reviewed baseline migration')
            self.write_environment(application, operator)
            self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'database')
            if self.revision() not in ('', BASELINE):
                raise ValueError('Existing database revision requires a reviewed compatibility decision')
            self.compose('run', '--rm', '--no-deps', 'provision')
            self.backup()
            self.compose('run', '--rm', '--no-deps', 'migrate')
            self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'candidate')
            self.validate_service('candidate')
            changed = True
            self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'brewery')
            self.validate_service('brewery')
            atomic_write(state_path, json.dumps({'application': application, 'operator': operator}))
            print('SUCCESS: UI/API deployment healthy.', flush=True)
        except Exception:
            if previous_env is not None:
                atomic_write(self.root / '.env', previous_env)
            if changed:
                if previous:
                    self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'brewery')
                    self.validate_service('brewery')
                else:
                    self.legacy_rollback()
                print('Previous application restored; database retained without downgrade.', flush=True)
            raise
        finally:
            # Candidate has no persistent state; leave PostgreSQL and its volume intact.
            self.compose('rm', '-s', '-f', 'candidate')


def main(arguments=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['deploy', 'backup', 'rollback-legacy'])
    parser.add_argument('commit', nargs='?')
    args = parser.parse_args(arguments)
    if os.geteuid() != 0:
        raise SystemExit('Use the installed administrator command; production files require root.')
    deployment = Deployment('/opt/beer-brewing-app/runtime', '/var/backups/beer-brewing-app')
    with deployment.locked():
        if args.operation == 'deploy':
            if not args.commit or not re.fullmatch('[0-9a-f]{40}', args.commit):
                raise SystemExit('Deployment requires a full lowercase Git commit SHA.')
            deployment.deploy_images(deployment.image(args.commit, 'app'), deployment.image(args.commit, 'operator'))
        elif args.operation == 'backup':
            deployment.backup()
        else:
            deployment.legacy_rollback()


if __name__ == '__main__':
    main()
