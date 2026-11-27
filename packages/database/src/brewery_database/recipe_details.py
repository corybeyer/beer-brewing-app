"""Transactional PostgreSQL persistence for optional recipe draft details."""
from functools import wraps

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from brewery_domain.recipe_details import RecipeDetails, VolumeTarget, normalize_details, validate_details
from brewery_domain.recipes import DraftConflict, DraftNotFound, InvalidDraft, RecipeStorageUnavailable


_metadata = sa.MetaData()
_version = sa.Table('recipe_version', _metadata,
                    sa.Column('id', sa.Text, primary_key=True),
                    sa.Column('status', sa.Text),
                    sa.Column('edit_revision', sa.BigInteger),
                    sa.Column('updated_at', sa.DateTime(timezone=True)))
_details = sa.Table('recipe_details', _metadata,
                    sa.Column('version_id', sa.Text, primary_key=True),
                    sa.Column('source', sa.Text))
_tag = sa.Table('recipe_tag', _metadata,
                sa.Column('version_id', sa.Text, primary_key=True),
                sa.Column('position', sa.Integer, primary_key=True),
                sa.Column('tag', sa.Text))
_target = sa.Table('recipe_volume_target', _metadata,
                   sa.Column('version_id', sa.Text, primary_key=True),
                   sa.Column('position', sa.Integer),
                   sa.Column('purpose', sa.Text, primary_key=True),
                   sa.Column('amount', sa.Numeric),
                   sa.Column('unit', sa.Text),
                   sa.UniqueConstraint('version_id', 'position'))


def _storage_errors(operation):
    @wraps(operation)
    def wrapped(*arguments, **options):
        try:
            return operation(*arguments, **options)
        except SQLAlchemyError:
            raise RecipeStorageUnavailable('Recipe storage is unavailable.') from None
    return wrapped


def _validate(details: RecipeDetails) -> RecipeDetails:
    normalized = normalize_details(details)
    issues = validate_details(normalized)
    if issues:
        raise InvalidDraft(issues)
    return normalized


def _write_details(connection, version_id: str, details: RecipeDetails) -> None:
    connection.execute(_details.insert().values(version_id=version_id, source=details.source))
    tags = [dict(version_id=version_id, position=index, tag=tag)
            for index, tag in enumerate(details.tags, 1)]
    targets = [dict(version_id=version_id, position=index, purpose=target.purpose,
                    amount=target.amount, unit=target.unit)
               for index, target in enumerate(details.volume_targets, 1)]
    if tags:
        connection.execute(_tag.insert(), tags)
    if targets:
        connection.execute(_target.insert(), targets)


def _read_details(connection, version_id: str) -> RecipeDetails:
    row = connection.execute(sa.select(_details).where(_details.c.version_id == version_id)).mappings().one_or_none()
    tags = connection.execute(sa.select(_tag.c.tag).where(_tag.c.version_id == version_id)
                              .order_by(_tag.c.position)).scalars().all()
    targets = connection.execute(sa.select(_target).where(_target.c.version_id == version_id)
                                 .order_by(_target.c.position)).mappings().all()
    return RecipeDetails(
        source=row['source'] if row is not None else None,
        tags=tuple(tags),
        volume_targets=tuple(VolumeTarget(row['purpose'], row['amount'], row['unit']) for row in targets),
    )


class PostgresRecipeDetailsStore:
    """Read and replace one version's details under the shared edit revision."""

    def __init__(self, engine: Engine):
        self.engine = engine

    @_storage_errors
    def load(self, version_id: str) -> tuple[int, RecipeDetails] | None:
        with self.engine.begin() as connection:
            # The shared version lock keeps metadata coherent with all other draft writes.
            row = connection.execute(sa.select(_version).where(_version.c.id == version_id)
                                     .with_for_update(read=True)).mappings().one_or_none()
            if row is None:
                return None
            return row['edit_revision'], _read_details(connection, version_id)

    @_storage_errors
    def save(self, version_id: str, expected_revision: int,
             details: RecipeDetails) -> tuple[int, RecipeDetails]:
        if type(expected_revision) is not int or not 1 <= expected_revision < 9223372036854775807:
            raise ValueError('Expected edit revision must be a positive integer below the storage limit.')
        normalized = _validate(details)
        with self.engine.begin() as connection:
            row = connection.execute(sa.select(_version).where(_version.c.id == version_id)
                                     .with_for_update()).mappings().one_or_none()
            if row is None:
                raise DraftNotFound('The recipe draft does not exist.')
            if row['status'] != 'draft' or row['edit_revision'] != expected_revision:
                raise DraftConflict('The draft changed; reload before saving recipe details.')
            row = connection.execute(_version.update().where(_version.c.id == version_id).values(
                edit_revision=expected_revision + 1,
                updated_at=sa.func.clock_timestamp(),
            ).returning(_version)).mappings().one()
            connection.execute(_target.delete().where(_target.c.version_id == version_id))
            connection.execute(_tag.delete().where(_tag.c.version_id == version_id))
            connection.execute(_details.delete().where(_details.c.version_id == version_id))
            _write_details(connection, version_id, normalized)
            return row['edit_revision'], normalized
