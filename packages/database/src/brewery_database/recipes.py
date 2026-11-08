"""Transactional PostgreSQL implementation of the domain draft storage port."""
from collections import defaultdict

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from brewery_domain.recipe_plan import Addition, Ingredient, RecipePlan, Step
from brewery_domain.recipes import (
    DraftConflict, DraftNotFound, InvalidDraft, RecipeDraft, StoredDraft, validate_draft,
)


# Runtime SQL descriptions only; historical migrations own schema creation.
_metadata = sa.MetaData()
_recipe = sa.Table('recipe', _metadata, sa.Column('id', sa.Text, primary_key=True))
_version = sa.Table('recipe_version', _metadata,
                    sa.Column('id', sa.Text, primary_key=True), sa.Column('recipe_id', sa.Text),
                    sa.Column('version_number', sa.Integer), sa.Column('status', sa.Text),
                    sa.Column('name', sa.Text), sa.Column('description', sa.Text),
                    sa.Column('edit_revision', sa.BigInteger),
                    sa.Column('updated_at', sa.DateTime(timezone=True)))
_ingredient = sa.Table('recipe_ingredient', _metadata,
                       sa.Column('version_id', sa.Text, primary_key=True),
                       sa.Column('id', sa.Text, primary_key=True), sa.Column('position', sa.Integer),
                       sa.Column('name', sa.Text), sa.Column('category', sa.Text),
                       sa.Column('quantity', sa.Numeric), sa.Column('unit', sa.Text))
_step = sa.Table('recipe_step', _metadata,
                sa.Column('version_id', sa.Text, primary_key=True),
                sa.Column('id', sa.Text, primary_key=True), sa.Column('position', sa.Integer),
                sa.Column('title', sa.Text), sa.Column('instructions', sa.Text),
                sa.Column('anchor_step_id', sa.Text))
_dependency = sa.Table('recipe_step_dependency', _metadata,
                      sa.Column('version_id', sa.Text, primary_key=True),
                      sa.Column('step_id', sa.Text, primary_key=True),
                      sa.Column('required_step_id', sa.Text, primary_key=True),
                      sa.Column('position', sa.Integer))
_addition = sa.Table('recipe_step_addition', _metadata,
                    sa.Column('version_id', sa.Text, primary_key=True),
                    sa.Column('position', sa.Integer, primary_key=True),
                    sa.Column('step_id', sa.Text), sa.Column('ingredient_id', sa.Text),
                    sa.Column('quantity', sa.Numeric), sa.Column('unit', sa.Text))


def _validate(draft):
    issues = validate_draft(draft)
    if issues:
        raise InvalidDraft(issues)


def _write_plan(connection, plan):
    ingredients = [dict(version_id=plan.version_id, id=item.id, position=index,
                        name=item.name, category=item.category, quantity=item.quantity, unit=item.unit)
                   for index, item in enumerate(plan.ingredients, 1)]
    steps = [dict(version_id=plan.version_id, id=item.id, position=index,
                  title=item.title, instructions=item.instructions, anchor_step_id=item.anchor_step_id)
             for index, item in enumerate(plan.steps, 1)]
    dependencies = [dict(version_id=plan.version_id, step_id=step.id,
                         required_step_id=key, position=index)
                    for step in plan.steps for index, key in enumerate(dict.fromkeys(step.dependencies), 1)]
    additions = [dict(version_id=plan.version_id, position=index, step_id=item.step_id,
                      ingredient_id=item.ingredient_id, quantity=item.quantity, unit=item.unit)
                 for index, item in enumerate(plan.additions, 1)]
    for table, rows in ((_ingredient, ingredients), (_step, steps),
                        (_dependency, dependencies), (_addition, additions)):
        if rows:
            connection.execute(table.insert(), rows)


def _read_plan(connection, version_id):
    def rows(table):
        return connection.execute(sa.select(table).where(table.c.version_id == version_id)
                                  .order_by(table.c.position)).mappings().all()

    dependencies = defaultdict(list)
    for row in rows(_dependency):
        dependencies[row['step_id']].append(row['required_step_id'])
    ingredients = tuple(Ingredient(id=row['id'], version_id=version_id,
                                   quantity=row['quantity'], unit=row['unit'],
                                   name=row['name'], category=row['category']) for row in rows(_ingredient))
    steps = tuple(Step(id=row['id'], version_id=version_id,
                       dependencies=tuple(dependencies[row['id']]), anchor_step_id=row['anchor_step_id'],
                       title=row['title'], instructions=row['instructions']) for row in rows(_step))
    additions = tuple(Addition(version_id, row['step_id'], row['ingredient_id'],
                               row['quantity'], row['unit']) for row in rows(_addition))
    return RecipePlan(version_id, ingredients, steps, additions)


def _stored(connection, row):
    return StoredDraft(RecipeDraft(row['recipe_id'], row['version_number'],
                                   _read_plan(connection, row['id']), row['name'], row['description']),
                       row['edit_revision'])


class PostgresRecipeDraftStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def create(self, draft: RecipeDraft) -> StoredDraft:
        try:
            with self.engine.begin() as connection:
                _validate(draft)
                connection.execute(insert(_recipe).values(id=draft.recipe_id).on_conflict_do_nothing())
                row = connection.execute(_version.insert().values(
                    id=draft.plan.version_id, recipe_id=draft.recipe_id,
                    version_number=draft.version_number, status='draft', name=draft.name,
                    description=draft.description, edit_revision=1,
                ).returning(_version)).mappings().one()
                _write_plan(connection, draft.plan)
                result = _stored(connection, row)
            return result
        except IntegrityError as error:
            if getattr(error.orig, 'sqlstate', None) == '23505':
                raise DraftConflict('That recipe version already exists.') from None
            raise

    def load(self, version_id: str) -> StoredDraft | None:
        with self.engine.begin() as connection:
            # The shared parent lock keeps all child reads coherent at READ COMMITTED.
            row = connection.execute(sa.select(_version).where(_version.c.id == version_id)
                                     .with_for_update(read=True)).mappings().one_or_none()
            return _stored(connection, row) if row is not None else None

    def save(self, draft: RecipeDraft, expected_revision: int) -> StoredDraft:
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('Expected edit revision must be a positive integer.')
        with self.engine.begin() as connection:
            row = connection.execute(sa.select(_version).where(_version.c.id == draft.plan.version_id)
                                     .with_for_update()).mappings().one_or_none()
            if row is None:
                raise DraftNotFound('The recipe draft does not exist.')
            if (row['edit_revision'] != expected_revision or row['status'] != 'draft'
                    or row['recipe_id'] != draft.recipe_id or row['version_number'] != draft.version_number):
                raise DraftConflict('The draft changed; reload before saving. Recipe/version identity cannot be changed.')
            _validate(draft)
            row = connection.execute(_version.update().where(_version.c.id == draft.plan.version_id).values(
                name=draft.name, description=draft.description, edit_revision=expected_revision + 1,
                updated_at=sa.func.clock_timestamp(),
            ).returning(_version)).mappings().one()
            for table in (_addition, _dependency, _step, _ingredient):
                connection.execute(table.delete().where(table.c.version_id == draft.plan.version_id))
            _write_plan(connection, draft.plan)
            result = _stored(connection, row)
        return result
