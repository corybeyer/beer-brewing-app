"""Recipe details preserve optional values under the shared optimistic revision."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from threading import Event
import time
from unittest.mock import patch
from uuid import uuid4

from alembic import command
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

import brewery_database.recipe_details as recipe_details
from brewery_database.recipe_details import PostgresRecipeDetailsStore
from brewery_database.recipes import PostgresRecipeDraftStore
from brewery_domain.recipe_details import RecipeDetails, VolumeTarget
from brewery_domain.recipe_plan import RecipePlan
from brewery_domain.recipes import DraftConflict, DraftNotFound, InvalidDraft, RecipeDraft, RecipeStorageUnavailable
from tests.fixtures.postgres_support import PostgreSQLTestCase


class RecipeDetailsTests(PostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        command.upgrade(self.config, 'head')
        self.details = PostgresRecipeDetailsStore(self.engine)
        self.recipes = PostgresRecipeDraftStore(self.engine)
        self.version_id = 'details-version'
        self.draft = RecipeDraft('details-recipe', 1, RecipePlan(self.version_id), 'Pale ale', None)
        self.recipes.create(self.draft)

    def scalar(self, statement):
        with self.engine.connect() as connection:
            return connection.execute(sa.text(statement)).scalar_one()

    def wait_for_blocked_connection(self):
        deadline = time.monotonic() + 5
        while not self.scalar("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock')"):
            if time.monotonic() >= deadline:
                self.fail('The second connection did not wait on a PostgreSQL lock')
            time.sleep(.01)

    def test_absent_values_and_ordered_details_round_trip_exactly(self):
        self.assertEqual(self.details.load(self.version_id), (1, RecipeDetails()))
        self.assertIsNone(self.details.load('missing'))
        value = RecipeDetails(
            'Book recipe, page 12 ',
            ('Citrus', 'Saison', 'Café'),
            (VolumeTarget('kettle', Decimal('23.125000000001'), 'L'),
             VolumeTarget('fermenter', Decimal('5.25'), 'US_gal')),
        )
        revision, saved = self.details.save(self.version_id, 1, value)
        expected = RecipeDetails(value.source, value.tags,
                                 (value.volume_targets[0], value.volume_targets[1]))
        self.assertEqual((revision, saved), (2, expected))
        self.assertEqual(self.details.load(self.version_id), (2, expected))
        self.assertEqual(self.recipes.load(self.version_id).edit_revision, 2)
        self.assertEqual(self.scalar("SELECT count(*) FROM recipe_details WHERE version_id = 'details-version'"), 1)

    def test_clear_details_keeps_version_and_increments_shared_revision(self):
        stored_revision, _ = self.details.save(self.version_id, 1, RecipeDetails(
            'Personal notes', ('Citrus',), (VolumeTarget('packaged', Decimal('18'), 'L'),)))
        self.assertEqual(stored_revision, 2)
        # Recipe-plan saves and detail saves participate in the same version revision.
        recipe_saved = self.recipes.save(self.draft, 2)
        self.assertEqual(recipe_saved.edit_revision, 3)
        details_revision, cleared = self.details.save(self.version_id, 3, RecipeDetails())
        self.assertEqual((details_revision, cleared), (4, RecipeDetails()))
        self.assertEqual(self.details.load(self.version_id), (4, RecipeDetails()))
        self.assertEqual(self.scalar("SELECT count(*) FROM recipe_tag WHERE version_id = 'details-version'"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM recipe_volume_target WHERE version_id = 'details-version'"), 0)

    def test_validation_and_stale_writes_leave_details_and_revision_unchanged(self):
        initial = RecipeDetails('Original source', ('Pale ale',),
                                (VolumeTarget('kettle', Decimal('25'), 'L'),))
        self.details.save(self.version_id, 1, initial)
        bad = (
            replace(initial, source='  '),
            replace(initial, tags=('Citrus', 'cITRUS')),
            replace(initial, tags=('x' * 101,)),
            replace(initial, volume_targets=(VolumeTarget('other', Decimal('10'), 'L'),)),
            replace(initial, volume_targets=(VolumeTarget('fermenter', Decimal('NaN'), 'L'),)),
            replace(initial, volume_targets=(VolumeTarget('fermenter', Decimal('1'), 'count'),)),
        )
        for candidate in bad:
            with self.subTest(candidate=candidate), self.assertRaises(InvalidDraft):
                self.details.save(self.version_id, 2, candidate)
            self.assertEqual(self.details.load(self.version_id), (2, initial))
        with self.assertRaises(DraftConflict):
            self.details.save(self.version_id, 1, RecipeDetails('stale', (), ()))
        self.assertEqual(self.details.load(self.version_id), (2, initial))
        with self.assertRaises(DraftNotFound):
            self.details.save('missing', 1, RecipeDetails())

    def test_write_failure_rolls_back_revision_and_all_details(self):
        original = RecipeDetails('Original source', ('Pale ale',),
                                 (VolumeTarget('fermenter', Decimal('19'), 'L'),))
        self.details.save(self.version_id, 1, original)
        with self.engine.begin() as connection:
            connection.execute(sa.text(
                "ALTER TABLE recipe_tag ADD CONSTRAINT fixture_rejection CHECK (tag <> 'rejected')"))
        changed = RecipeDetails('New source', ('rejected',),
                                (VolumeTarget('kettle', Decimal('25'), 'L'),))
        with self.assertRaises(RecipeStorageUnavailable):
            self.details.save(self.version_id, 2, changed)
        self.assertEqual(self.details.load(self.version_id), (2, original))

    def test_database_checks_and_version_ownership_reject_invalid_rows(self):
        for statement in (
            "INSERT INTO recipe_details (version_id, source) VALUES ('foreign', 'source')",
            "INSERT INTO recipe_tag (version_id, position, tag) VALUES ('foreign', 1, 'Citrus')",
            "INSERT INTO recipe_volume_target (version_id, position, purpose, amount, unit) VALUES ('foreign', 1, 'kettle', 1, 'L')",
        ):
            with self.subTest(statement=statement), self.assertRaises(IntegrityError):
                with self.engine.begin() as connection:
                    connection.execute(sa.text(statement))
        with self.engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO recipe_details (version_id, source) VALUES ('details-version', NULL)"))
        for statement in (
            "INSERT INTO recipe_tag (version_id, position, tag) VALUES ('details-version', 1, '  Citrus')",
            "INSERT INTO recipe_volume_target (version_id, position, purpose, amount, unit) VALUES ('details-version', 1, 'fermenter', 'NaN', 'L')",
            "INSERT INTO recipe_volume_target (version_id, position, purpose, amount, unit) VALUES ('details-version', 1, 'unknown', 1, 'L')",
            "INSERT INTO recipe_volume_target (version_id, position, purpose, amount, unit) VALUES ('details-version', 1, 'fermenter', 1, 'count')",
        ):
            with self.subTest(statement=statement), self.assertRaises(IntegrityError):
                with self.engine.begin() as connection:
                    connection.execute(sa.text(statement))

    def test_overlapping_detail_writers_serialize_on_recipe_version(self):
        first_details = RecipeDetails('First writer', ('one',), ())
        second_details = RecipeDetails('Second writer', ('two',), ())
        locked, release = Event(), Event()
        write_details = recipe_details._write_details

        def hold_first(connection, version_id, details):
            locked.set()
            if not release.wait(10):
                raise RuntimeError('Timed out waiting to release test writer')
            write_details(connection, version_id, details)

        with ThreadPoolExecutor(max_workers=2) as workers:
            with patch('brewery_database.recipe_details._write_details', side_effect=hold_first):
                first = workers.submit(self.details.save, self.version_id, 1, first_details)
                try:
                    self.assertTrue(locked.wait(5))
                    second = workers.submit(self.details.save, self.version_id, 1, second_details)
                    self.wait_for_blocked_connection()
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=5), (2, first_details))
                with self.assertRaises(DraftConflict):
                    second.result(timeout=5)
        self.assertEqual(self.details.load(self.version_id), (2, first_details))


class RecipeDetailsMigrationPrivilegeTests(PostgreSQLTestCase):
    """The migration grants only CRUD on the tables owned by this adapter."""

    def setUp(self):
        super().setUp()
        self.role = 'recipe_details_' + uuid4().hex
        with self.engine.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{self.role}"'))
        self.addCleanup(self.drop_role)
        self.config.attributes['application_role'] = self.role
        command.upgrade(self.config, 'head')

    def drop_role(self):
        with self.engine.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{self.role}"'))
            connection.execute(sa.text(f'DROP ROLE "{self.role}"'))

    def test_new_application_grants_are_table_scoped(self):
        with self.engine.connect() as connection:
            for table in ('recipe_details', 'recipe_tag', 'recipe_volume_target'):
                for privilege in ('SELECT', 'INSERT', 'DELETE'):
                    self.assertTrue(connection.execute(sa.text(
                        'SELECT has_table_privilege(:role, :table, :privilege)'),
                        {'role': self.role, 'table': table, 'privilege': privilege}).scalar_one())
            for table in ('recipe_details', 'recipe_tag', 'recipe_volume_target'):
                for privilege in ('UPDATE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'):
                    self.assertFalse(connection.execute(sa.text(
                        'SELECT has_table_privilege(:role, :table, :privilege)'),
                        {'role': self.role, 'table': table, 'privilege': privilege}).scalar_one())
