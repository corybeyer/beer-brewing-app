"""Version-owned source, tags, and volume targets for recipe drafts."""
from alembic import context, op
import sqlalchemy as sa


revision = '0005_recipe_details'
down_revision = '0004_conversion_proposals'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep this historical DDL independent of mutable runtime table definitions.
    op.execute("""CREATE TABLE recipe_details (
        version_id text PRIMARY KEY REFERENCES recipe_version(id) ON DELETE RESTRICT,
        source text CHECK (source IS NULL OR
            (length(source) BETWEEN 1 AND 2000 AND btrim(source) <> ''))
    )""")
    op.execute("""CREATE TABLE recipe_tag (
        version_id text NOT NULL REFERENCES recipe_details(version_id) ON DELETE RESTRICT,
        position integer NOT NULL CHECK (position BETWEEN 1 AND 32),
        tag text NOT NULL CHECK (
            length(tag) BETWEEN 1 AND 100 AND tag = btrim(tag)),
        PRIMARY KEY (version_id, position),
        UNIQUE (version_id, tag)
    )""")
    op.execute("""CREATE TABLE recipe_volume_target (
        version_id text NOT NULL REFERENCES recipe_details(version_id) ON DELETE RESTRICT,
        position integer NOT NULL CHECK (position BETWEEN 1 AND 3),
        purpose text NOT NULL CHECK (purpose IN ('fermenter', 'kettle', 'packaged')),
        amount numeric NOT NULL CHECK (
            amount > 0 AND amount < 1000000000000 AND scale(amount) <= 12),
        unit text NOT NULL CHECK (unit IN ('mL', 'L', 'US_fl_oz', 'US_gal')),
        PRIMARY KEY (version_id, purpose),
        UNIQUE (version_id, position)
    )""")

    application = context.config.attributes.get('application_role')
    if application is not None:
        role = op.get_bind().dialect.identifier_preparer.quote_identifier(application)
        op.execute(f'GRANT SELECT, INSERT, DELETE ON TABLE recipe_details, recipe_tag, '
                   f'recipe_volume_target TO {role}')


def downgrade() -> None:
    connection = op.get_bind()
    tables = ('recipe_version', 'recipe_details', 'recipe_tag', 'recipe_volume_target')
    connection.execute(sa.text('LOCK TABLE ' + ', '.join(tables) + ' IN ACCESS EXCLUSIVE MODE'))
    if any(connection.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM {table})')).scalar_one()
           for table in ('recipe_details', 'recipe_tag', 'recipe_volume_target')):
        raise RuntimeError('Recipe detail data exists; downgrade requires a reviewed data-preservation plan.')
    for table in ('recipe_volume_target', 'recipe_tag', 'recipe_details'):
        op.execute(f'DROP TABLE {table}')
