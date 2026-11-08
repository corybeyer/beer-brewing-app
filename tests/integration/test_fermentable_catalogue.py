"""Real PostgreSQL catalogue transactions, historical data, and migration guards."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from threading import Barrier, Event
import time
from unittest.mock import patch

from alembic import command
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError

from brewery_database.catalogue import PostgresFermentableCatalog
from brewery_database.connection import SCHEMA_REVISION
from brewery_database.recipes import PostgresRecipeDraftStore
from brewery_domain.fermentable_catalogue import CatalogConflict, CatalogUnavailable, GrainComponent, InvalidCatalogRevision
from brewery_domain.recipe_plan import RecipePlan
from brewery_domain.recipes import RecipeDraft
from tests.fixtures.catalogue_support import grain, extract
from tests.fixtures.postgres_support import PostgreSQLTestCase


class FermentableCatalogStorageTests(PostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        command.upgrade(self.config, 'head')
        self.store = PostgresFermentableCatalog(self.engine)

    def known_extract(self):
        self.store.append(grain())
        self.store.append(grain('grain-r2', 'second-grain'))
        value = extract()
        self.store.append(value)
        return value

    def test_round_trip_exact_sources_ranges_tags_and_known_blend(self):
        value = self.known_extract()
        self.assertEqual(self.store.load(value.revision_id), value)
        self.assertEqual(self.store.load('grain-r1'), grain())
        self.assertIsNone(self.store.load('missing'))
        unknown = replace(grain('unknown-r1', 'unknown'), potential_ppg=None, potential_status='unknown', potential_note=None, color=None)
        self.store.append(unknown)
        self.assertEqual(self.store.load(unknown.revision_id), unknown)

    def test_revisions_append_without_rewriting_historical_profiles(self):
        original = grain()
        self.store.append(original)
        changed = replace(original, revision_id='grain-new', revision_number=2, name='Changed name', potential_ppg=Decimal('38'))
        self.store.append(changed)
        self.assertEqual(self.store.load(original.revision_id), original)
        self.assertEqual(self.store.load(changed.revision_id), changed)
        for duplicate in (replace(original, name='Forbidden overwrite'), replace(original, revision_id='duplicate-number'),
                          replace(changed, revision_id='wrong-kind', revision_number=3, kind='lme')):
            with self.assertRaises(CatalogConflict):
                self.store.append(duplicate)
        self.assertEqual(self.store.load(original.revision_id), original)

    def test_missing_or_non_grain_components_and_partial_bills_leave_no_orphans(self):
        original = self.known_extract()
        for component in ('missing', original.revision_id):
            value = replace(original, product_id='failed-product', revision_id='failed-revision',
                            components=(GrainComponent(component, Decimal('1')),))
            with self.assertRaises(InvalidCatalogRevision):
                self.store.append(value)
            self.assertIsNone(self.store.load('failed-revision'))
            with self.engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT count(*) FROM fermentable_product WHERE id = 'failed-product'")).scalar_one(), 0)
        with self.assertRaises(InvalidCatalogRevision):
            self.store.append(replace(original, revision_id='partial', revision_number=2, components=original.components[:1]))
        self.assertEqual(self.store.load(original.revision_id), original)

    def test_real_database_failure_rolls_back_parent_and_children(self):
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE fermentable_flavor ADD CONSTRAINT fixture_failure CHECK (descriptor <> 'toasty')"))
        with self.assertRaises(CatalogUnavailable) as error:
            self.store.append(grain())
        self.assertNotIn('fixture_failure', str(error.exception))
        with self.engine.connect() as connection:
            for table in ('fermentable_product', 'fermentable_revision', 'fermentable_flavor'):
                self.assertEqual(connection.execute(text(f'SELECT count(*) FROM {table}')).scalar_one(), 0)

    def test_sql_enforces_finite_values_color_context_and_component_kind(self):
        original = self.known_extract()
        for sql in ("UPDATE fermentable_revision SET potential_ppg = 'NaN' WHERE id = 'grain-r1'",
                    "UPDATE fermentable_revision SET potential_ppg = 0 WHERE id = 'grain-r1'",
                    "UPDATE fermentable_revision SET potential_ppg = 37.1234567890123 WHERE id = 'grain-r1'",
                    "UPDATE fermentable_revision SET color_basis = NULL WHERE id = 'grain-r1'",
                    "UPDATE fermentable_revision SET source_retrieved_at = 'infinity' WHERE id = 'grain-r1'",
                    "UPDATE fermentable_component SET grain_revision_id = 'extract-r1' WHERE extract_revision_id = 'extract-r1'",
                    "UPDATE fermentable_product SET kind = 'dme' WHERE id = 'grain'",
                    "UPDATE fermentable_flavor SET descriptor = 'Not A Tag' WHERE revision_id = 'grain-r1'"):
            with self.subTest(sql=sql):
                with self.assertRaises(IntegrityError), self.engine.begin() as connection:
                    connection.execute(text(sql))
        self.assertEqual(self.store.load(original.revision_id), original)

    def test_loaded_cross_row_anomalies_are_not_returned_as_trusted_profiles(self):
        self.known_extract()
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE fermentable_component SET mass_fraction = 0.5 WHERE extract_revision_id = 'extract-r1' AND position = 1"))
        with self.assertRaises(CatalogUnavailable):
            self.store.load('extract-r1')

    def test_overlapping_duplicate_appends_have_one_authoritative_revision(self):
        barrier = Barrier(2)
        value = grain()
        def append():
            barrier.wait(timeout=5)
            try:
                self.store.append(value)
                return 'created'
            except CatalogConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(append) for _ in range(2)]
            self.assertEqual(sorted(future.result(timeout=10) for future in futures), ['conflict', 'created'])
        self.assertEqual(self.store.load(value.revision_id), value)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT count(*) FROM fermentable_product')).scalar_one(), 1)

    def test_populated_catalogue_refuses_downgrade_without_losing_data(self):
        original = self.known_extract()
        with self.assertRaisesRegex(RuntimeError, 'Catalogue data exists'):
            command.downgrade(self.config, '0002_recipe_drafts')
        self.assertEqual(self.store.load(original.revision_id), original)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(), SCHEMA_REVISION)

    def test_empty_catalogue_downgrade_and_populated_recipe_upgrade_preserve_recipes(self):
        draft = RecipeDraft('retained', 1, RecipePlan('retained-version'), 'Retained recipe')
        recipes = PostgresRecipeDraftStore(self.engine)
        recipes.create(draft)
        command.downgrade(self.config, '0002_recipe_drafts')
        self.assertEqual(recipes.load('retained-version').draft, draft)
        with self.engine.connect() as connection:
            self.assertIsNone(connection.execute(text("SELECT to_regclass('fermentable_revision')")).scalar_one())
        command.upgrade(self.config, 'head')
        command.upgrade(self.config, 'head')
        self.assertEqual(recipes.load('retained-version').draft, draft)
        self.store.append(grain())
        self.assertEqual(self.store.load('grain-r1'), grain())

    def test_unavailable_storage_does_not_expose_connection_details(self):
        engine = create_engine(self.url.set(database='missing_catalogue_database'), connect_args={'connect_timeout': 1})
        self.addCleanup(engine.dispose)
        with self.assertRaises(CatalogUnavailable) as error:
            PostgresFermentableCatalog(engine).load('anything')
        self.assertNotIn(self.url.username, str(error.exception))
        self.assertNotIn(self.url.password, str(error.exception))


    def test_downgrade_waits_for_inflight_append_then_refuses_data_loss(self):
        locked, release = Event(), Event()
        def hold_revision(connection, cursor, statement, parameters, context, many):
            if statement.startswith('INSERT INTO fermentable_revision'):
                locked.set()
                if not release.wait(10):
                    raise RuntimeError('Timed out releasing catalogue append')
        event.listen(self.engine, 'before_cursor_execute', hold_revision)
        self.addCleanup(event.remove, self.engine, 'before_cursor_execute', hold_revision)
        with ThreadPoolExecutor(max_workers=2) as workers:
            appending = workers.submit(self.store.append, grain())
            try:
                self.assertTrue(locked.wait(5))
                downgrading = workers.submit(command.downgrade, self.config, '0002_recipe_drafts')
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with self.engine.connect() as connection:
                        blocked = connection.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock' AND query LIKE 'LOCK TABLE fermentable_product%')")).scalar_one()
                    if blocked:
                        break
                    time.sleep(.01)
                self.assertTrue(blocked)
            finally:
                release.set()
            self.assertEqual(appending.result(timeout=5), grain())
            with self.assertRaisesRegex(RuntimeError, 'Catalogue data exists'):
                downgrading.result(timeout=5)
        self.assertEqual(self.store.load('grain-r1'), grain())
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one(), SCHEMA_REVISION)
