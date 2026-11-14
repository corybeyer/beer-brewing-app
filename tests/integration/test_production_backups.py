"""Actual PostgreSQL 17 snapshots/dumps/restores while another connection writes."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch

from alembic import command
import psycopg
from sqlalchemy import text

from infrastructure.deployment.production.rollout import Deployment, SQLSession
from brewery_database.catalogue import PostgresFermentableCatalog
from brewery_database.connection import SCHEMA_REVISION
from tests.fixtures.catalogue_support import grain, extract
from tests.fixtures.postgres_support import PostgreSQLTestCase


class PostgreSQLDeployment(Deployment):
    """Route only the disposable fixture to local tools or its CI service container."""
    def __init__(self, root, url):
        super().__init__(root, root / 'backups')
        self.url = url

    def arguments(self, arguments):
        arguments = list(arguments)
        if '-d' in arguments:
            index = arguments.index('-d') + 1
            if arguments[index] == 'brewery':
                arguments[index] = self.url.database
        if '-U' in arguments:
            arguments[arguments.index('-U') + 1] = self.url.username
        container = os.environ.get('TEST_POSTGRES_CONTAINER')
        if container:
            return ['/usr/bin/docker', 'exec', '-i', container, *arguments]
        directory = os.environ.get('POSTGRES_TEST_BIN')
        executable = str(Path(directory) / arguments[0]) if directory else shutil.which(arguments[0])
        if not executable:
            raise RuntimeError('PostgreSQL 17 client tools required: set POSTGRES_TEST_BIN or TEST_POSTGRES_CONTAINER.')
        return [executable, *arguments[1:]]

    def environment(self):
        return {**os.environ, 'PGHOST': self.url.host or self.url.query.get('host', ''),
                'PGPORT': str(self.url.port or 5432), 'PGPASSWORD': self.url.password or ''}

    def compose(self, *arguments, input=None):
        assert arguments[:3] == ('exec', '-T', 'database')
        return subprocess.check_output(self.arguments(arguments[3:]), input=input,
                                       env=self.environment(), timeout=60, stderr=subprocess.PIPE)

    def sql_session(self):
        return SQLSession(self.arguments(['psql', '-XqAt', '-v', 'ON_ERROR_STOP=1',
                                          '-U', 'brewery_admin', '-d', 'brewery']), self.environment())


class ProductionBackupTests(PostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        command.upgrade(self.config, 'head')
        self.directory = TemporaryDirectory(prefix='brewery-snapshot-test-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'secrets').mkdir(mode=0o700)
        for name in ('admin-password', 'migrator-password', 'app-password'):
            (self.root / 'secrets' / name).write_text(secrets.token_hex(24))
        self.deployment = PostgreSQLDeployment(self.root, self.url)
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE backup_fixture (id integer PRIMARY KEY, amount integer NOT NULL)'))
            connection.execute(text('INSERT INTO backup_fixture VALUES (1, 0)'))

    def snapshot_sessions(self):
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                                           "AND application_name = 'brewery_backup_snapshot'")).scalar_one()

    def test_dump_and_verification_share_snapshot_while_writes_continue(self):
        start, written, stop = Event(), Event(), Event()
        errors = []

        def writer():
            try:
                with psycopg.connect(self.url.set(drivername='postgresql').render_as_string(hide_password=False),
                                     autocommit=True) as connection:
                    if not start.wait(5):
                        raise RuntimeError('Dump did not start')
                    while not stop.is_set():
                        connection.execute('UPDATE backup_fixture SET amount = amount + 1')
                        written.set()
                        stop.wait(.01)
            except Exception as error:
                errors.append(error)
                written.set()

        compose = self.deployment.compose

        def during_dump(*arguments, **options):
            if 'pg_dump' in arguments:
                start.set()
                self.assertTrue(written.wait(5))
                self.assertFalse(errors)
            return compose(*arguments, **options)

        thread = Thread(target=writer)
        thread.start()
        try:
            with patch.object(self.deployment, 'compose', side_effect=during_dump):
                backup = self.deployment.backup()
        finally:
            stop.set()
            start.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        with self.engine.connect() as connection:
            self.assertGreater(connection.execute(text('SELECT amount FROM backup_fixture')).scalar_one(), 0)
        metadata = json.loads((backup / 'metadata.json').read_text())
        self.assertTrue(metadata['verified'])
        self.assertEqual(metadata['consistency'], 'exported-snapshot')
        self.assertGreater((backup / 'database.dump').stat().st_size, 0)
        self.assertEqual(self.snapshot_sessions(), 0)
        self.assertFalse(self.deployment.sql("SELECT datname FROM pg_database WHERE datname LIKE 'brew_verify_%'", 'postgres'))

    def test_dump_failure_releases_snapshot_and_keeps_prior_backup(self):
        prior = self.deployment.backup()
        compose = self.deployment.compose

        def fail(*arguments, **options):
            if 'pg_dump' in arguments:
                raise RuntimeError('simulated dump failure')
            return compose(*arguments, **options)

        with patch.object(self.deployment, 'compose', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'dump failure'):
                self.deployment.backup()
        self.assertEqual(list(self.deployment.backups.iterdir()), [prior])
        self.assertEqual(self.snapshot_sessions(), 0)

    def test_snapshot_sql_failure_releases_session_and_publishes_nothing(self):
        @contextmanager
        def invalid_snapshot():
            with Deployment.snapshot(self.deployment) as session:
                session.sql('SELECT missing_snapshot_fixture_column')
                yield session

        with patch.object(self.deployment, 'snapshot', invalid_snapshot):
            with self.assertRaisesRegex(RuntimeError, 'session ended'):
                self.deployment.backup()
        self.assertEqual(list(self.deployment.backups.iterdir()), [])
        self.assertEqual(self.snapshot_sessions(), 0)

    def test_snapshot_query_timeout_closes_the_transaction(self):
        with self.assertRaisesRegex(RuntimeError, 'timed out'):
            with self.deployment.snapshot() as session:
                session.sql('SELECT pg_sleep(2)', timeout=.02)
        self.assertEqual(self.snapshot_sessions(), 0)

    def test_retention_keeps_seven_verified_sets_and_unrelated_directory(self):
        self.deployment.backups.mkdir(mode=0o700)
        unrelated = self.deployment.backups / 'unrelated'
        unrelated.mkdir(mode=0o700)
        for _ in range(9):
            self.deployment.backup()
        self.assertEqual(len(list(self.deployment.backups.glob('brewery-*'))), 7)
        self.assertTrue(unrelated.is_dir())


    def test_catalogue_sources_components_and_flavors_survive_verified_restore(self):
        store = PostgresFermentableCatalog(self.engine)
        store.append(grain())
        store.append(grain('grain-r2', 'second-grain'))
        store.append(extract())
        fingerprint = self.deployment.table_fingerprints
        restored = []
        def inspect_restore(database='brewery', query=None):
            if database.startswith('brew_verify_'):
                restored.append(database)
                self.assertEqual(self.deployment.sql("SELECT count(*) FROM fermentable_revision", database), '3')
                self.assertEqual(self.deployment.sql("SELECT source_label FROM fermentable_revision WHERE id = 'extract-r1'", database), 'Synthetic test data')
                self.assertEqual(self.deployment.sql("SELECT string_agg(mass_fraction::text, ',' ORDER BY position) FROM fermentable_component WHERE extract_revision_id = 'extract-r1'", database), '0.9,0.1')
                self.assertEqual(self.deployment.sql("SELECT string_agg(descriptor, ',' ORDER BY position) FROM fermentable_flavor WHERE revision_id = 'extract-r1'", database), 'malty,toasty')
            return fingerprint(database, query)
        with patch.object(self.deployment, 'table_fingerprints', side_effect=inspect_restore):
            backup = self.deployment.backup()
        self.assertEqual(len(restored), 1)
        metadata = json.loads((backup / 'metadata.json').read_text())
        self.assertTrue(metadata['verified'])
        self.assertEqual(metadata['revision'], SCHEMA_REVISION)


    def test_complete_exact_proposal_document_survives_verified_restore(self):
        from brewery_database.proposals import PostgresConversionProposalStore
        from tests.fixtures.proposal_support import seed_proposal
        value = seed_proposal(self.engine)
        store = PostgresConversionProposalStore(self.engine)
        store.append(value)
        with self.engine.connect() as connection:
            source_document = connection.execute(text('SELECT document FROM conversion_proposal')).scalar_one()
        fingerprint = self.deployment.table_fingerprints
        restored = []
        def inspect_restore(database='brewery', query=None):
            if database.startswith('brew_verify_'):
                restored.append(database)
                self.assertEqual(self.deployment.sql('SELECT count(*) FROM conversion_proposal', database), '1')
                self.assertEqual(json.loads(self.deployment.sql('SELECT document::text FROM conversion_proposal', database)), source_document)
                self.assertEqual(self.deployment.sql('SELECT original_edit_revision FROM conversion_proposal', database), '1')
            return fingerprint(database, query)
        with patch.object(self.deployment, 'table_fingerprints', side_effect=inspect_restore):
            backup = self.deployment.backup()
        self.assertEqual(len(restored), 1)
        metadata = json.loads((backup / 'metadata.json').read_text())
        self.assertTrue(metadata['verified'])
        self.assertEqual(metadata['revision'], SCHEMA_REVISION)
        self.assertEqual(store.load(value.id), value)
