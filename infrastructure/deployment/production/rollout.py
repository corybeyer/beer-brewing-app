"""Root-installed deployment/backup operations; no application-runtime imports."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
import pwd
from pathlib import Path
import re
import select
import shutil
import stat
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener
import uuid


REPOSITORY = 'ghcr.io/corybeyer/beer-brewing-app'
BASELINE = '0001_baseline'
RECIPES = '0002_recipe_drafts'
SUPPORTED_REVISIONS = {BASELINE, RECIPES}
DATA_VOLUME = 'brewery-production-postgres'


class SQLSession:
    """Bounded psql command channel; no database drivers in root operations."""
    def __init__(self, arguments, environment):
        self.process = subprocess.Popen(arguments, env=environment, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.pending = b''

    def sql(self, statement, timeout=600):
        marker = ('__brewery_' + uuid.uuid4().hex + '__').encode()
        try:
            self.process.stdin.write(statement.rstrip(';').encode() + b';\n\\echo ' + marker + b'\n')
            self.process.stdin.flush()
            deadline = time.monotonic() + timeout
            while True:
                position = self.pending.find(marker + b'\n')
                if position >= 0:
                    result = self.pending[:position]
                    self.pending = self.pending[position + len(marker) + 1:]
                    return result.decode().strip()
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                    raise RuntimeError('Snapshot SQL session timed out')
                data = os.read(self.process.stdout.fileno(), 65536)
                if not data:
                    raise RuntimeError('Snapshot SQL session ended before completing its query')
                self.pending += data
        except (OSError, ValueError) as error:
            raise RuntimeError('Snapshot SQL session failed') from error

    def close(self):
        try:
            self.process.stdin.close()  # EOF closes the connection and rolls back.
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        finally:
            self.process.stdout.close()


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

    def sql_session(self):
        arguments = ['/usr/bin/docker', 'compose', '--env-file', str(self.root / '.env'),
                     '-f', str(self.root / 'compose.yaml'), 'exec', '-T', 'database',
                     'psql', '-XqAt', '-v', 'ON_ERROR_STOP=1', '-U', 'brewery_admin', '-d', 'brewery']
        return SQLSession(arguments, {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                                     'HOME': pwd.getpwuid(os.geteuid()).pw_dir})

    @contextmanager
    def snapshot(self):
        session = self.sql_session()
        try:
            session.sql("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; "
                        "SET LOCAL idle_in_transaction_session_timeout = '15min'; "
                        "SET LOCAL statement_timeout = '10min'; "
                        "SET LOCAL application_name = 'brewery_backup_snapshot'")
            yield session
        finally:
            session.close()

    def compose(self, *arguments, input=None):
        return self.command('compose', '--env-file', str(self.root / '.env'),
                            '-f', str(self.root / 'compose.yaml'), *arguments, input=input)

    @contextmanager
    def locked(self):
        descriptor = os.open(self.root / 'operation.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'a') as lock:
            details = os.fstat(lock.fileno())
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid() or details.st_mode & 0o077:
                raise ValueError('Operation lock must be an owned private regular file')
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
            'BREWERY_DATA_VOLUME': DATA_VOLUME,
            'BREWERY_BIND_ADDRESS': '0.0.0.0', 'BREWERY_HTTP_PORT': '8080',
            **self.settings,
        }
        if any('\n' in str(value) or '\r' in str(value) for value in values.values()):
            raise ValueError('Deployment settings must be single-line values')
        # JSON quoting is valid Compose dotenv double-quoted syntax.
        atomic_write(self.root / '.env', ''.join(f'{key}={json.dumps(str(value))}\n' for key, value in values.items()))

    def sql(self, statement, database='brewery'):
        return self.compose('exec', '-T', 'database', 'psql', '-U', 'brewery_admin', '-d', database,
                            '-v', 'ON_ERROR_STOP=1', '-XqAtc', statement).decode().strip()

    def revision(self, database='brewery', query=None):
        query = query or (lambda statement: self.sql(statement, database))
        exists = query("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        return query('SELECT version_num FROM public.alembic_version ORDER BY version_num') if exists == 't' else ''

    def table_fingerprints(self, database='brewery', query=None):
        query = query or (lambda statement: self.sql(statement, database))
        def canonical(statement):
            return query("SET TIME ZONE 'UTC'; SET datestyle = 'ISO, YMD'; "
                         "SET extra_float_digits = 3; " + statement)
        # Server formats identifiers; never interpolate table names into SQL ourselves.
        queries = canonical("SELECT format($query$SELECT %L, count(*), md5(coalesce(string_agg("
                           "md5(row_to_json(r)::text), '' ORDER BY md5(row_to_json(r)::text)), '')) "
                           "FROM %I.%I AS r$query$, schemaname || '.' || tablename, "
                           "schemaname, tablename) FROM pg_tables WHERE schemaname NOT IN "
                           "('pg_catalog', 'information_schema') ORDER BY schemaname, tablename")
        return [canonical(statement) for statement in queries.splitlines()]

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
            with self.snapshot() as snapshot:
                snapshot_id = snapshot.sql('SELECT pg_export_snapshot()')
                if not re.fullmatch(r'[0-9A-Fa-f]+-[0-9A-Fa-f]+-[0-9]+', snapshot_id):
                    raise ValueError('Database returned an invalid exported snapshot identifier')
                revision = self.revision(query=snapshot.sql)
                fingerprints = self.table_fingerprints(query=snapshot.sql)
                with (stage / 'database.dump').open('wb') as dump:
                    os.chmod(dump.name, 0o600)
                    dump.write(self.compose('exec', '-T', 'database', 'pg_dump', '-U', 'brewery_admin',
                                            '-d', 'brewery', '--format=custom', '--snapshot', snapshot_id))
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
            atomic_write(stage / 'metadata.json', json.dumps({'format': 2, 'revision': revision, 'verified': True,
                         'consistency': 'exported-snapshot',
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
        migration_attempted = False
        original_revision = None
        previous_schema = None
        try:
            # Permit only reviewed pairs and forward transitions, never arbitrary heads.
            schema = self.command('run', '--rm', '--network', 'none', '--entrypoint', 'python', application,
                                  '-c', 'from brewery_database.connection import SCHEMA_REVISION; print(SCHEMA_REVISION)').decode().strip()
            heads = self.command('run', '--rm', '--network', 'none', '--entrypoint', 'python', operator,
                                 '-c', 'from alembic.config import Config; from alembic.script import ScriptDirectory; '
                                 'print(",".join(ScriptDirectory.from_config(Config("alembic.ini")).get_heads()))').decode().strip()
            if schema not in SUPPORTED_REVISIONS or heads != schema:
                raise ValueError('Deployment requires a matching, explicitly reviewed schema pair')
            if previous:
                previous_schema = self.command('run', '--rm', '--network', 'none', '--entrypoint', 'python',
                                               previous['application'], '-c',
                                               'from brewery_database.connection import SCHEMA_REVISION; print(SCHEMA_REVISION)').decode().strip()
                if previous_schema not in SUPPORTED_REVISIONS:
                    raise ValueError('Previous application has an unreviewed schema contract')
            self.write_environment(application, operator)
            self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'database')
            original_revision = self.revision()
            permitted = {'', BASELINE} if schema == BASELINE else {'', BASELINE, RECIPES}
            if original_revision not in permitted:
                raise ValueError('Existing database revision requires a reviewed compatibility decision')
            self.compose('run', '--rm', '--no-deps', 'provision')
            self.backup()
            migration_attempted = True
            self.compose('run', '--rm', '--no-deps', 'migrate')
            if self.revision() != schema:
                raise ValueError('Migration did not produce the declared application schema')
            self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'candidate')
            self.validate_service('candidate')
            changed = True
            self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'brewery')
            self.validate_service('brewery')
            atomic_write(state_path, json.dumps({'application': application, 'operator': operator, 'schema': schema}))
            print('SUCCESS: UI/API deployment healthy.', flush=True)
        except Exception:
            if previous_env is not None:
                atomic_write(self.root / '.env', previous_env)
            resulting_revision = original_revision
            if migration_attempted:
                try:
                    resulting_revision = self.revision()
                except Exception:
                    resulting_revision = None  # An unknown result cannot justify old-API rollback.
            if changed or (migration_attempted and (resulting_revision != original_revision
                                                     or previous and resulting_revision != previous_schema)):
                if previous and resulting_revision == previous_schema:
                    try:
                        self.compose('up', '-d', '--wait', '--wait-timeout', '120', 'brewery')
                        self.validate_service('brewery')
                    except Exception:
                        self.legacy_rollback()
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
