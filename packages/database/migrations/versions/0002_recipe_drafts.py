"""Version-scoped draft plans; no publication or brewing execution state."""
from alembic import context, op
import sqlalchemy as sa


revision = '0002_recipe_drafts'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep this historical DDL independent of mutable runtime table definitions.
    for statement in (
        """CREATE TABLE recipe (
            id text PRIMARY KEY CHECK (id <> '' AND id = btrim(id)),
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE recipe_version (
            id text PRIMARY KEY CHECK (id <> '' AND id = btrim(id)),
            recipe_id text NOT NULL REFERENCES recipe(id) ON DELETE RESTRICT,
            version_number integer NOT NULL CHECK (version_number > 0),
            status text NOT NULL DEFAULT 'draft' CHECK (status = 'draft'),
            name text CHECK (name IS NULL OR btrim(name) <> ''),
            description text,
            edit_revision bigint NOT NULL DEFAULT 1 CHECK (edit_revision > 0),
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (recipe_id, version_number)
        )""",
        """CREATE TABLE recipe_ingredient (
            version_id text NOT NULL REFERENCES recipe_version(id) ON DELETE RESTRICT,
            id text NOT NULL CHECK (id <> '' AND id = btrim(id)),
            position integer NOT NULL CHECK (position > 0),
            name text,
            category text CHECK (category IN ('grain', 'hops', 'yeast', 'other')),
            quantity numeric CHECK (quantity > 0 AND quantity < 'Infinity'::numeric),
            unit text CHECK (unit IN ('g','kg','oz','lb','mL','L','US_fl_oz','US_gal','count','packet')),
            CHECK (category NOT IN ('grain', 'hops') OR unit IN ('g','kg','oz','lb')),
            PRIMARY KEY (version_id, id), UNIQUE (version_id, position)
        )""",
        """CREATE TABLE recipe_step (
            version_id text NOT NULL REFERENCES recipe_version(id) ON DELETE RESTRICT,
            id text NOT NULL CHECK (id <> '' AND id = btrim(id)),
            position integer NOT NULL CHECK (position > 0),
            title text, instructions text, anchor_step_id text,
            PRIMARY KEY (version_id, id), UNIQUE (version_id, position),
            CHECK (anchor_step_id IS NULL OR anchor_step_id <> id),
            FOREIGN KEY (version_id, anchor_step_id) REFERENCES recipe_step(version_id, id)
                ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
        )""",
        """CREATE TABLE recipe_step_dependency (
            version_id text NOT NULL, step_id text NOT NULL, required_step_id text NOT NULL,
            position integer NOT NULL CHECK (position > 0),
            PRIMARY KEY (version_id, step_id, required_step_id),
            UNIQUE (version_id, step_id, position), CHECK (step_id <> required_step_id),
            FOREIGN KEY (version_id, step_id) REFERENCES recipe_step(version_id, id)
                ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY (version_id, required_step_id) REFERENCES recipe_step(version_id, id)
                ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
        )""",
        """CREATE TABLE recipe_step_addition (
            version_id text NOT NULL, position integer NOT NULL CHECK (position > 0),
            step_id text NOT NULL, ingredient_id text NOT NULL,
            quantity numeric CHECK (quantity > 0 AND quantity < 'Infinity'::numeric),
            unit text CHECK (unit IN ('g','kg','oz','lb','mL','L','US_fl_oz','US_gal','count','packet')),
            PRIMARY KEY (version_id, position),
            FOREIGN KEY (version_id, step_id) REFERENCES recipe_step(version_id, id)
                ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY (version_id, ingredient_id) REFERENCES recipe_ingredient(version_id, id)
                ON DELETE NO ACTION DEFERRABLE INITIALLY DEFERRED
        )""",
    ):
        op.execute(statement)
    application = context.config.attributes.get('application_role')
    if application is not None:
        role = op.get_bind().dialect.identifier_preparer.quote_identifier(application)
        op.execute(f'GRANT SELECT, INSERT ON TABLE recipe TO {role}')
        op.execute(f'GRANT SELECT, INSERT, UPDATE ON TABLE recipe_version TO {role}')
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE recipe_ingredient, recipe_step, '
                   f'recipe_step_dependency, recipe_step_addition TO {role}')


def downgrade() -> None:
    connection = op.get_bind()
    # Hold writers out until the emptiness decision and DDL commit together.
    connection.execute(sa.text('LOCK TABLE recipe, recipe_version, recipe_ingredient, recipe_step, '
                               'recipe_step_dependency, recipe_step_addition IN ACCESS EXCLUSIVE MODE'))
    if any(connection.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM {table})')).scalar_one()
           for table in ('recipe', 'recipe_version', 'recipe_ingredient', 'recipe_step',
                         'recipe_step_dependency', 'recipe_step_addition')):
        raise RuntimeError('Recipe data exists; downgrade requires a reviewed data-preservation plan.')
    for table in ('recipe_step_addition', 'recipe_step_dependency', 'recipe_step',
                  'recipe_ingredient', 'recipe_version', 'recipe'):
        op.execute(f'DROP TABLE {table}')
