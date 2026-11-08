"""Real PostgreSQL M2 draft migration, ownership, atomicity, and concurrency."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from threading import Event
import time
from unittest.mock import patch

from alembic import command
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from brewery_database import recipes
from brewery_database.connection import SCHEMA_REVISION, database_is_ready
from brewery_domain.recipe_plan import Addition, Ingredient, RecipePlan, Step, UNITS
from brewery_domain.recipes import DraftConflict, DraftNotFound, InvalidDraft, RecipeDraft
from tests.fixtures.postgres_support import PostgreSQLTestCase


class RecipeDraftTests(PostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        command.upgrade(self.config, 'head')
        self.store = recipes.PostgresRecipeDraftStore(self.engine)

    def draft(self, version='v1', number=1):
        plan = RecipePlan(version,
                          (Ingredient('hops', version, Decimal('100.000000000000000001'), 'g', 'Cascade', 'hops'),),
                          (Step('boil', version, title='Confirm rolling boil'),
                           Step('late', version, ('boil',), 'boil', 'Add aroma hops', 'Brewer confirms addition.')),
                          (Addition(version, 'late', 'hops', Decimal('20.000000000000000001'), 'g'),))
        return RecipeDraft('recipe-1', number, plan, 'Test pale ale', 'Manual plan')

    def scalar(self, statement):
        with self.engine.connect() as connection:
            return connection.execute(sa.text(statement)).scalar_one()

    def wait_for_blocked_connection(self):
        deadline = time.monotonic() + 5
        while not self.scalar("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock')"):
            if time.monotonic() >= deadline:
                self.fail('The second connection did not wait on a PostgreSQL lock')
            time.sleep(.01)

    def test_complete_and_incomplete_drafts_round_trip_without_rounding(self):
        draft = self.draft()
        created = self.store.create(draft)
        self.assertEqual(created.draft, draft)
        self.assertEqual(self.store.load('v1'), created)
        self.assertEqual(created.edit_revision, 1)
        empty = RecipeDraft('empty-recipe', 1, RecipePlan('empty-version', (Ingredient('yeast', 'empty-version'),)))
        self.assertEqual(self.store.create(empty).draft, empty)
        self.assertIsNone(self.store.load('empty-version').draft.plan.ingredients[0].quantity)
        self.assertTrue(self.scalar('SELECT created_at IS NOT NULL AND updated_at IS NOT NULL FROM recipe_version WHERE id = \'v1\''))

    def test_reorder_and_replace_plan_preserves_identity_and_other_versions(self):
        draft = self.draft()
        self.store.create(draft)
        sibling = self.store.create(self.draft('v2', 2))
        changed = replace(draft, name='Changed', plan=replace(draft.plan, steps=tuple(reversed(draft.plan.steps))))
        saved = self.store.save(changed, 1)
        self.assertEqual(saved.draft, changed)
        self.assertEqual(saved.edit_revision, 2)
        self.assertEqual(self.store.load('v2'), sibling)
        empty = replace(changed, plan=RecipePlan('v1'))
        self.assertEqual(self.store.save(empty, 2).draft, empty)
        self.assertEqual(self.scalar("SELECT count(*) FROM recipe_step WHERE version_id = 'v1'"), 0)

    def test_validation_failures_preserve_prior_version_and_edit_revision(self):
        draft = self.draft()
        original = self.store.create(draft)
        bad_plans = (
            replace(draft.plan, steps=(Step('boil', 'v1', ('late',)), Step('late', 'v1', anchor_step_id='boil'))),
            replace(draft.plan, additions=(Addition('v1', 'late', 'foreign-hop', Decimal('1'), 'g'),)),
            replace(draft.plan, ingredients=(replace(draft.plan.ingredients[0], version_id='v2'),)),
            replace(draft.plan, additions=draft.plan.additions * 6),
        )
        for plan in bad_plans:
            with self.subTest(plan=plan):
                with self.assertRaises(InvalidDraft) as caught:
                    self.store.save(replace(draft, plan=plan), 1)
                self.assertTrue(caught.exception.issues)
                self.assertEqual(self.store.load('v1'), original)

    def test_invalid_create_and_duplicate_identity_leave_no_orphan_recipe(self):
        draft = self.draft()
        with self.assertRaises(InvalidDraft):
            self.store.create(replace(draft, plan=replace(draft.plan, steps=(Step('boil', 'v2'),))))
        self.assertEqual(self.scalar('SELECT count(*) FROM recipe'), 0)
        original = self.store.create(draft)
        for duplicate in (replace(draft, recipe_id='orphan'), self.draft('different-version', 1)):
            with self.assertRaises(DraftConflict):
                self.store.create(duplicate)
        self.assertEqual(self.scalar('SELECT count(*) FROM recipe'), 1)
        self.assertEqual(self.store.load('v1'), original)

    def test_database_failure_after_replacement_starts_rolls_back_all_changes(self):
        draft = self.draft()
        original = self.store.create(draft)
        with self.engine.begin() as connection:
            connection.execute(sa.text("ALTER TABLE recipe_ingredient ADD CONSTRAINT fixture_rejection CHECK (name <> 'rejected by database')"))
        changed = replace(draft, name='Must roll back', plan=replace(draft.plan, ingredients=(
            replace(draft.plan.ingredients[0], name='rejected by database'),)))
        with self.assertRaises(IntegrityError):
            self.store.save(changed, 1)
        self.assertEqual(self.store.load('v1'), original)

    def test_stale_edits_and_identity_changes_are_rejected(self):
        draft = self.draft()
        self.store.create(draft)
        updated = self.store.save(replace(draft, name='newer'), 1)
        for changed, expected in ((draft, 1), (replace(draft, recipe_id='wrong'), 2),
                                  (replace(draft, version_number=2), 2)):
            with self.assertRaises(DraftConflict):
                self.store.save(changed, expected)
        self.assertEqual(self.store.load('v1'), updated)
        self.assertIsNone(self.store.load('missing'))
        with self.assertRaises(DraftNotFound):
            self.store.save(replace(draft, plan=RecipePlan('missing')), 1)

    def test_overlapping_writers_serialize_and_only_one_edit_wins(self):
        draft = self.draft()
        self.store.create(draft)
        locked, release = Event(), Event()
        write_plan = recipes._write_plan

        def hold_first(connection, plan):
            locked.set()
            if not release.wait(10):
                raise RuntimeError('Timed out waiting to release test writer')
            write_plan(connection, plan)

        with ThreadPoolExecutor(max_workers=2) as workers:
            with patch.object(recipes, '_write_plan', side_effect=hold_first):
                first = workers.submit(self.store.save, replace(draft, name='first writer'), 1)
                try:
                    self.assertTrue(locked.wait(5))
                    second = workers.submit(self.store.save, replace(draft, name='second writer'), 1)
                    self.wait_for_blocked_connection()
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=5).draft.name, 'first writer')
                with self.assertRaises(DraftConflict):
                    second.result(timeout=5)
        self.assertEqual(self.store.load('v1').edit_revision, 2)

    def test_database_foreign_keys_reject_cross_version_links(self):
        self.store.create(self.draft())
        other = RecipeDraft('recipe-2', 1, RecipePlan('v2', (Ingredient('foreign-hop', 'v2'),),
                                                    (Step('foreign-step', 'v2'),)))
        self.store.create(other)
        for statement in (
            "INSERT INTO recipe_step_addition VALUES ('v1', 2, 'late', 'foreign-hop', 1, 'g')",
            "INSERT INTO recipe_step_addition VALUES ('v1', 2, 'foreign-step', 'hops', 1, 'g')",
            "INSERT INTO recipe_step_dependency VALUES ('v1', 'late', 'foreign-step', 2)",
            "UPDATE recipe_step SET anchor_step_id = 'foreign-step' WHERE version_id = 'v1' AND id = 'boil'",
        ):
            with self.subTest(statement=statement):
                with self.assertRaises(IntegrityError):
                    with self.engine.begin() as connection:
                        connection.execute(sa.text(statement))

    def test_reader_waits_for_replacement_and_observes_one_complete_revision(self):
        draft = self.draft()
        self.store.create(draft)
        changed = replace(draft, name='Replacement', plan=RecipePlan('v1'))
        locked, release = Event(), Event()
        write_plan = recipes._write_plan

        def hold_replacement(connection, plan):
            locked.set()
            if not release.wait(10):
                raise RuntimeError('Timed out waiting to release test replacement')
            write_plan(connection, plan)

        with ThreadPoolExecutor(max_workers=2) as workers:
            with patch.object(recipes, '_write_plan', side_effect=hold_replacement):
                saving = workers.submit(self.store.save, changed, 1)
                try:
                    self.assertTrue(locked.wait(5))
                    reading = workers.submit(self.store.load, 'v1')
                    self.wait_for_blocked_connection()
                finally:
                    release.set()
                self.assertEqual(reading.result(timeout=5), saving.result(timeout=5))
        self.assertEqual(self.store.load('v1').draft, changed)

    def test_repeated_dependency_links_are_normalized_without_losing_anchor(self):
        draft = self.draft()
        late = replace(draft.plan.steps[1], dependencies=('boil', 'boil'))
        proposed = replace(draft, plan=replace(draft.plan, steps=(draft.plan.steps[0], late)))
        stored = self.store.create(proposed)
        self.assertEqual(stored.draft, draft)

    def test_database_checks_reject_invalid_values_and_self_references(self):
        self.store.create(self.draft())
        for value in ('0', '-1', 'NaN', 'Infinity', '-Infinity'):
            with self.subTest(quantity=value):
                with self.assertRaises(IntegrityError):
                    with self.engine.begin() as connection:
                        connection.execute(sa.text("UPDATE recipe_ingredient SET quantity = CAST(:value AS numeric)"), {'value': value})
        for statement in (
            "UPDATE recipe_ingredient SET unit = 'unsupported'",
            "UPDATE recipe_ingredient SET category = 'unsupported'",
            "UPDATE recipe_ingredient SET unit = 'L' WHERE category = 'hops'",
            "UPDATE recipe_step SET anchor_step_id = id",
            "INSERT INTO recipe_step_dependency VALUES ('v1', 'boil', 'boil', 1)",
            "UPDATE recipe_version SET status = 'published'",
            "UPDATE recipe_version SET version_number = 0",
            "DELETE FROM recipe_version",
        ):
            with self.subTest(statement=statement):
                with self.assertRaises(IntegrityError):
                    with self.engine.begin() as connection:
                        connection.execute(sa.text(statement))

    def test_unit_catalogue_round_trips_every_supported_token(self):
        draft = self.draft()
        for index, unit in enumerate(sorted(UNITS), 1):
            plan = RecipePlan(f'units-{index}', (Ingredient('ingredient', f'units-{index}', Decimal('1'), unit),))
            proposed = replace(draft, version_number=index, plan=plan)
            self.assertEqual(self.store.create(proposed).draft, proposed)

    def test_populated_recipe_downgrade_is_refused_without_data_loss(self):
        original = self.store.create(self.draft())
        with self.assertRaisesRegex(RuntimeError, 'data-preservation'):
            command.downgrade(self.config, '0001_baseline')
        self.assertEqual(self.scalar('SELECT version_num FROM alembic_version'), SCHEMA_REVISION)
        self.assertEqual(self.store.load('v1'), original)
        command.upgrade(self.config, 'head')
        self.assertEqual(self.store.load('v1'), original)

    def test_upgrade_populated_baseline_and_empty_downgrade_preserve_fixture(self):
        command.downgrade(self.config, '0001_baseline')
        self.assertFalse(database_is_ready(self.engine))
        with self.engine.begin() as connection:
            connection.execute(sa.text('CREATE TABLE retained_fixture (note text NOT NULL)'))
            connection.execute(sa.text("INSERT INTO retained_fixture VALUES ('preserve me')"))
        command.upgrade(self.config, 'head')
        command.upgrade(self.config, 'head')
        self.assertTrue(database_is_ready(self.engine))
        self.assertEqual(self.scalar('SELECT note FROM retained_fixture'), 'preserve me')
        command.downgrade(self.config, '0001_baseline')
        self.assertIsNone(self.scalar("SELECT to_regclass('recipe')"))
        self.assertEqual(self.scalar('SELECT note FROM retained_fixture'), 'preserve me')

    def test_downgrade_waits_for_inflight_create_and_then_refuses_data_loss(self):
        locked, release = Event(), Event()
        write_plan = recipes._write_plan

        def hold_create(connection, plan):
            locked.set()
            if not release.wait(10):
                raise RuntimeError('Timed out waiting to release test create')
            write_plan(connection, plan)

        with ThreadPoolExecutor(max_workers=2) as workers:
            with patch.object(recipes, '_write_plan', side_effect=hold_create):
                creating = workers.submit(self.store.create, self.draft())
                try:
                    self.assertTrue(locked.wait(5))
                    downgrading = workers.submit(command.downgrade, self.config, '0001_baseline')
                    self.wait_for_blocked_connection()
                finally:
                    release.set()
                original = creating.result(timeout=5)
                with self.assertRaisesRegex(RuntimeError, 'data-preservation'):
                    downgrading.result(timeout=5)
        self.assertEqual(self.store.load('v1'), original)
        self.assertEqual(self.scalar('SELECT version_num FROM alembic_version'), SCHEMA_REVISION)
