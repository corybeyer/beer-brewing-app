"""Append-only PostgreSQL catalogue adapter; recipes are independent of products."""
from functools import wraps

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from brewery_domain.fermentable_catalogue import (
    CatalogConflict, CatalogIssue, CatalogRevision, CatalogUnavailable, GrainComponent,
    IngredientColor, InvalidCatalogRevision, validate_catalog_revision,
)


_metadata = sa.MetaData()
_product = sa.Table('fermentable_product', _metadata,
    sa.Column('id', sa.Text, primary_key=True), sa.Column('kind', sa.Text))
_scalar_fields = ('product_id', 'kind', 'revision_number', 'name', 'manufacturer',
                  'source_label', 'source_url', 'source_retrieved_at', 'potential_ppg',
                  'potential_status', 'potential_note', 'flavor_notes',
                  'composition_status', 'composition_note')
_revision = sa.Table('fermentable_revision', _metadata,
    sa.Column('id', sa.Text, primary_key=True),
    *[sa.Column(field, sa.Integer if field == 'revision_number' else
        sa.DateTime(timezone=True) if field == 'source_retrieved_at' else
        sa.Numeric() if field == 'potential_ppg' else sa.Text) for field in _scalar_fields],
    sa.Column('color_low', sa.Numeric()), sa.Column('color_high', sa.Numeric()),
    sa.Column('color_unit', sa.Text), sa.Column('color_basis', sa.Text))
_flavor = sa.Table('fermentable_flavor', _metadata,
    sa.Column('revision_id', sa.Text), sa.Column('position', sa.Integer), sa.Column('descriptor', sa.Text))
_component = sa.Table('fermentable_component', _metadata,
    sa.Column('extract_revision_id', sa.Text), sa.Column('extract_kind', sa.Text),
    sa.Column('position', sa.Integer), sa.Column('grain_revision_id', sa.Text),
    sa.Column('mass_fraction', sa.Numeric()))


def _available(operation):
    @wraps(operation)
    def wrapped(*args, **options):
        try:
            return operation(*args, **options)
        except SQLAlchemyError:
            raise CatalogUnavailable('The fermentable catalogue is unavailable.') from None
    return wrapped


class PostgresFermentableCatalog:
    def __init__(self, engine):
        self.engine = engine

    @_available
    def append(self, value: CatalogRevision) -> CatalogRevision:
        issues = validate_catalog_revision(value)
        if issues:
            raise InvalidCatalogRevision(issues)
        try:
            with self.engine.begin() as connection:
                connection.execute(insert(_product).values(id=value.product_id, kind=value.kind)
                                   .on_conflict_do_nothing(index_elements=['id']))
                kind = connection.execute(sa.select(_product.c.kind).where(_product.c.id == value.product_id)).scalar_one()
                if kind != value.kind:
                    raise CatalogConflict('A product cannot change its fermentable kind.')
                if value.components:
                    ids = [item.grain_revision_id for item in value.components]
                    kinds = dict(connection.execute(sa.select(_revision.c.id, _revision.c.kind).where(_revision.c.id.in_(ids))).all())
                    issues = [CatalogIssue('unknown_grain', f'components[{index}].grain_revision_id',
                                           'Choose an existing grain revision.')
                              for index, item in enumerate(value.components) if kinds.get(item.grain_revision_id) != 'grain']
                    if issues:
                        raise InvalidCatalogRevision(issues)
                values = {field: getattr(value, field) for field in _scalar_fields}
                values.update(id=value.revision_id,
                    color_low=value.color.low if value.color else None,
                    color_high=value.color.high if value.color else None,
                    color_unit=value.color.unit if value.color else None,
                    color_basis=value.color.basis if value.color else None)
                connection.execute(_revision.insert().values(**values))
                if value.flavor_tags:
                    connection.execute(_flavor.insert(), [dict(revision_id=value.revision_id, position=index + 1, descriptor=tag)
                                                          for index, tag in enumerate(value.flavor_tags)])
                if value.components:
                    connection.execute(_component.insert(), [dict(extract_revision_id=value.revision_id, extract_kind=value.kind,
                        position=index + 1, grain_revision_id=item.grain_revision_id, mass_fraction=item.mass_fraction)
                        for index, item in enumerate(value.components)])
            return value
        except IntegrityError as error:
            if getattr(error.orig, 'sqlstate', None) == '23505':
                raise CatalogConflict('That product revision already exists.') from None
            if getattr(error.orig, 'sqlstate', None) == '23503':
                raise InvalidCatalogRevision((CatalogIssue('unknown_grain', 'components', 'Choose existing grain revisions.'),)) from None
            raise

    @_available
    def load(self, revision_id: str) -> CatalogRevision | None:
        with self.engine.connect() as connection:
            return _read_revision(connection, revision_id)

    @_available
    def list_grains(self, limit: int = 1000) -> tuple[CatalogRevision, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Catalogue page is outside its supported bounds.')
        with self.engine.connect() as connection:
            rows = connection.execute(sa.select(_revision.c.id).where(_revision.c.kind == 'grain')
                                      .order_by(_revision.c.name, _revision.c.id).limit(limit)).scalars()
            return tuple(value for revision_id in rows
                         if (value := _read_revision(connection, revision_id)) is not None)


def _read_revision(connection, revision_id):
    row = connection.execute(sa.select(_revision).where(_revision.c.id == revision_id)).mappings().one_or_none()
    if row is None:
        return None
    tags = tuple(connection.execute(sa.select(_flavor.c.descriptor)
                 .where(_flavor.c.revision_id == revision_id).order_by(_flavor.c.position)).scalars())
    components = tuple(GrainComponent(item['grain_revision_id'], item['mass_fraction']) for item in
        connection.execute(sa.select(_component).where(_component.c.extract_revision_id == revision_id)
                           .order_by(_component.c.position)).mappings())
    color = IngredientColor(row['color_low'], row['color_high'], row['color_unit'], row['color_basis']) if row['color_low'] is not None else None
    value = CatalogRevision(revision_id=row['id'], **{field: row[field] for field in _scalar_fields},
                            color=color, flavor_tags=tags, components=components)
    if validate_catalog_revision(value):
        raise CatalogUnavailable('Stored catalogue data failed validation.')
    return value
