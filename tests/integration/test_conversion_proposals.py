"""Real PostgreSQL retention, recipe-lock concurrency, and migration safety."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event
import time

from alembic import command
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError

from brewery_database.connection import SCHEMA_REVISION
from brewery_database.proposals import PostgresConversionProposalStore
from brewery_database.recipes import PostgresRecipeDraftStore
from brewery_domain.conversion_proposals import (
    ConversionProposalConflict, ConversionProposalUnavailable, InvalidConversionProposal,
    StaleConversionProposal,
)
from brewery_domain.recipes import DraftConflict
from tests.fixtures.postgres_support import PostgreSQLTestCase
from tests.fixtures.proposal_support import proposal, seed_proposal


class ConversionProposalStorageTests(PostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        command.upgrade(self.config, 'head')
        self.store = PostgresConversionProposalStore(self.engine)
        self.recipes = PostgresRecipeDraftStore(self.engine)

    def count(self):
        with self.engine.connect() as connection:
            return connection.execute(text('SELECT count(*) FROM conversion_proposal')).scalar_one()

    def wait_blocked(self, pattern):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with self.engine.connect() as connection:
                blocked = connection.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock' AND query LIKE :pattern)"), {'pattern': pattern}).scalar_one()
            if blocked:
                return
            time.sleep(.01)
        self.fail('Expected concurrent operation to wait on its database lock')

    def test_exact_roundtrip_across_new_store_and_connection_preserves_history(self):
        value = seed_proposal(self.engine)
        self.assertEqual(self.store.append(value), value)
        self.assertIsNone(self.store.load('missing'))
        independent = create_engine(self.url)
        self.addCleanup(independent.dispose)
        self.assertEqual(PostgresConversionProposalStore(independent).load(value.id), value)
        changed = replace(value.original.draft, name='Changed live recipe')
        self.recipes.save(changed, 1)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE fermentable_revision SET name='Changed catalogue'"))
        self.assertEqual(self.store.load(value.id), value)
        self.assertEqual(self.recipes.load('v1').edit_revision, 2)

    def test_apply_replaces_plan_atomically_and_rejects_a_second_apply(self):
        value = seed_proposal(self.engine)
        self.store.append(value)
        applied = self.store.apply(value.id, value.original.edit_revision)
        self.assertEqual(applied.edit_revision, value.original.edit_revision + 1)
        self.assertEqual(applied.draft.plan.ingredients, value.proposed.plan.ingredients)
        self.assertEqual(applied.draft.plan.additions, value.proposed.plan.additions)
        self.assertEqual(applied.draft.name, value.original.draft.name)
        with self.assertRaises(DraftConflict):
            self.store.apply(value.id, applied.edit_revision)
        self.assertEqual(self.recipes.load(value.original.draft.plan.version_id), applied)

    def test_stale_missing_and_same_revision_different_content_save_nothing(self):
        value = proposal()
        with self.assertRaises(StaleConversionProposal):
            self.store.append(value)
        value = seed_proposal(self.engine)
        forged = replace(value,
            original=replace(value.original, draft=replace(value.original.draft, description='Different original')),
            proposed=replace(value.proposed, description='Different original'))
        with self.assertRaises(StaleConversionProposal):
            self.store.append(forged)
        self.recipes.save(replace(value.original.draft, name='New name'), 1)
        with self.assertRaises(StaleConversionProposal):
            self.store.append(value)
        self.assertEqual(self.count(), 0)

    def test_invalid_calculation_or_authoritative_catalogue_copy_saves_nothing(self):
        value = seed_proposal(self.engine)
        for invalid in (replace(value, conversions=()),
                        replace(value, catalogue=(replace(value.catalogue[0], name='Forged profile'),)),
                        replace(value, catalogue=(replace(value.catalogue[0], revision_id='missing'),),
                                conversions=(replace(value.conversions[0], target_catalogue_revision_id='missing'),))):
            with self.subTest(invalid=invalid.id), self.assertRaises(InvalidConversionProposal):
                self.store.append(invalid)
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.recipes.load('v1'), value.original)

    def test_duplicate_concurrent_appends_have_one_authoritative_proposal(self):
        value = seed_proposal(self.engine)
        barrier = Barrier(2)
        def append():
            barrier.wait(5)
            try:
                self.store.append(value)
                return 'created'
            except ConversionProposalConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(append) for _ in range(2)]
            self.assertEqual(sorted(future.result(10) for future in futures), ['conflict', 'created'])
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.store.load(value.id), value)

    def test_real_sql_failure_rolls_back_without_exposing_driver_details(self):
        value = seed_proposal(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text('ALTER TABLE conversion_proposal ADD CONSTRAINT synthetic_failure CHECK (false)'))
        with self.assertRaises(ConversionProposalUnavailable) as error:
            self.store.append(value)
        self.assertNotIn('synthetic_failure', str(error.exception))
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.recipes.load('v1'), value.original)

    def test_corrupt_snapshot_is_unavailable_and_sql_ties_headers_to_document(self):
        value = seed_proposal(self.engine)
        self.store.append(value)
        for sql in ("UPDATE conversion_proposal SET original_edit_revision=2",
                    "UPDATE conversion_proposal SET id='different'",
                    "UPDATE conversion_proposal SET document='{}'::jsonb",
                    "UPDATE conversion_proposal SET created_at='infinity'::timestamptz"):
            with self.subTest(sql=sql), self.assertRaises(IntegrityError), self.engine.begin() as connection:
                connection.execute(text(sql))
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE conversion_proposal SET document=jsonb_set(document, '{fields,conversions,0,fields,result,fields,amount}', '{\"fraction\":[\"5\",\"1\"]}'::jsonb)"))
        with self.assertRaises(ConversionProposalUnavailable):
            self.store.load(value.id)

    def test_append_holds_recipe_share_lock_until_insert_commits(self):
        value = seed_proposal(self.engine)
        held, release = Event(), Event()
        def hold(connection, cursor, statement, parameters, context, many):
            if statement.startswith('INSERT INTO conversion_proposal'):
                held.set()
                if not release.wait(10):
                    raise RuntimeError('Timed out releasing proposal insert')
        event.listen(self.engine, 'before_cursor_execute', hold)
        self.addCleanup(event.remove, self.engine, 'before_cursor_execute', hold)
        with ThreadPoolExecutor(max_workers=2) as workers:
            appending = workers.submit(self.store.append, value)
            try:
                self.assertTrue(held.wait(5))
                writing = workers.submit(self.recipes.save, replace(value.original.draft, name='Concurrent edit'), 1)
                self.wait_blocked('%FOR UPDATE%')
            finally:
                release.set()
            self.assertEqual(appending.result(5), value)
            self.assertEqual(writing.result(5).edit_revision, 2)
        self.assertEqual(self.store.load(value.id), value)

    def test_append_waits_for_inflight_recipe_edit_then_rejects_stale_input(self):
        value = seed_proposal(self.engine)
        held, release = Event(), Event()
        def hold(connection, cursor, statement, parameters, context, many):
            if statement.startswith('UPDATE recipe_version'):
                held.set()
                if not release.wait(10):
                    raise RuntimeError('Timed out releasing recipe edit')
        event.listen(self.engine, 'before_cursor_execute', hold)
        self.addCleanup(event.remove, self.engine, 'before_cursor_execute', hold)
        with ThreadPoolExecutor(max_workers=2) as workers:
            writing = workers.submit(self.recipes.save, replace(value.original.draft, description='Concurrent edit'), 1)
            try:
                self.assertTrue(held.wait(5))
                appending = workers.submit(self.store.append, value)
                self.wait_blocked('%FOR SHARE%')
            finally:
                release.set()
            self.assertEqual(writing.result(5).edit_revision, 2)
            with self.assertRaises(StaleConversionProposal):
                appending.result(5)
        self.assertEqual(self.count(), 0)

    def test_populated_upgrade_empty_downgrade_and_populated_refusal(self):
        command.downgrade(self.config, '0003_fermentable_catalogue')
        value = seed_proposal(self.engine)
        command.upgrade(self.config, 'head')
        command.upgrade(self.config, 'head')
        self.assertEqual(self.recipes.load('v1'), value.original)
        command.downgrade(self.config, '0003_fermentable_catalogue')
        self.assertEqual(self.recipes.load('v1'), value.original)
        command.upgrade(self.config, 'head')
        self.store.append(value)
        with self.assertRaisesRegex(RuntimeError, 'Proposal data exists'):
            command.downgrade(self.config, '0003_fermentable_catalogue')
        self.assertEqual(self.store.load(value.id), value)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(), SCHEMA_REVISION)

    def test_downgrade_waits_for_inflight_append_and_refuses_data_loss(self):
        value = seed_proposal(self.engine)
        held, release = Event(), Event()
        def hold(connection, cursor, statement, parameters, context, many):
            if statement.startswith('INSERT INTO conversion_proposal'):
                held.set()
                if not release.wait(10):
                    raise RuntimeError('Timed out releasing proposal insert')
        event.listen(self.engine, 'after_cursor_execute', hold)
        self.addCleanup(event.remove, self.engine, 'after_cursor_execute', hold)
        with ThreadPoolExecutor(max_workers=2) as workers:
            appending = workers.submit(self.store.append, value)
            try:
                self.assertTrue(held.wait(5))
                downgrading = workers.submit(command.downgrade, self.config, '0003_fermentable_catalogue')
                self.wait_blocked('LOCK TABLE conversion_proposal%')
            finally:
                release.set()
            self.assertEqual(appending.result(5), value)
            with self.assertRaisesRegex(RuntimeError, 'Proposal data exists'):
                downgrading.result(5)
        self.assertEqual(self.store.load(value.id), value)

    def test_unavailable_storage_sanitizes_connection_details(self):
        engine = create_engine(self.url.set(database='missing_proposals_database'), connect_args={'connect_timeout': 1})
        self.addCleanup(engine.dispose)
        with self.assertRaises(ConversionProposalUnavailable) as error:
            PostgresConversionProposalStore(engine).load('anything')
        self.assertNotIn(self.url.username, str(error.exception))
        self.assertNotIn(self.url.password, str(error.exception))
