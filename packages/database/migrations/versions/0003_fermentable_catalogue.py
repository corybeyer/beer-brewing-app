"""Sourced immutable fermentable revisions; no recipe links or proposals."""
from alembic import context, op
import sqlalchemy as sa


revision = '0003_fermentable_catalogue'
down_revision = '0002_recipe_drafts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in (
        """CREATE TABLE fermentable_product (
            id text PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 128 AND id = btrim(id)),
            kind text NOT NULL CHECK (kind IN ('grain','dme','lme')),
            UNIQUE (id, kind)
        )""",
        """CREATE TABLE fermentable_revision (
            id text PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 128 AND id = btrim(id)),
            product_id text NOT NULL, kind text NOT NULL,
            revision_number integer NOT NULL CHECK (revision_number > 0),
            name text NOT NULL CHECK (length(name) <= 200 AND btrim(name) <> ''),
            manufacturer text CHECK (length(manufacturer) <= 200 AND btrim(manufacturer) <> ''),
            source_label text NOT NULL CHECK (length(source_label) <= 200 AND btrim(source_label) <> ''),
            source_url text CHECK (length(source_url) <= 2048 AND btrim(source_url) <> ''),
            source_retrieved_at timestamptz NOT NULL CHECK (source_retrieved_at > '-infinity'::timestamptz AND source_retrieved_at < 'infinity'::timestamptz),
            potential_ppg numeric CHECK (potential_ppg > 0 AND potential_ppg < 1000000000000 AND scale(potential_ppg) <= 12),
            potential_status text NOT NULL CHECK (potential_status IN ('unknown','manufacturer','manual_assumption')),
            potential_note text CHECK (length(potential_note) <= 4000 AND btrim(potential_note) <> ''),
            color_low numeric, color_high numeric, color_unit text, color_basis text,
            flavor_notes text CHECK (length(flavor_notes) <= 4000 AND btrim(flavor_notes) <> ''),
            composition_status text NOT NULL CHECK (composition_status IN ('unknown','manufacturer','manual_assumption')),
            composition_note text CHECK (length(composition_note) <= 4000 AND btrim(composition_note) <> ''),
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (product_id, revision_number), UNIQUE (id, kind),
            FOREIGN KEY (product_id, kind) REFERENCES fermentable_product(id, kind) ON DELETE RESTRICT,
            CHECK ((potential_status = 'unknown' AND potential_ppg IS NULL) OR (potential_status <> 'unknown' AND potential_ppg IS NOT NULL)),
            CHECK (potential_status <> 'manual_assumption' OR potential_note IS NOT NULL),
            CHECK (composition_status <> 'manual_assumption' OR composition_note IS NOT NULL),
            CHECK ((potential_status <> 'manufacturer' AND composition_status <> 'manufacturer') OR (source_url IS NOT NULL AND manufacturer IS NOT NULL)),
            CHECK (kind <> 'grain' OR composition_status = 'unknown'),
            CHECK ((color_low IS NULL AND color_high IS NULL AND color_unit IS NULL AND color_basis IS NULL) OR
                   (color_low IS NOT NULL AND color_high IS NOT NULL AND color_unit IS NOT NULL AND color_basis IS NOT NULL
                    AND color_low >= 0 AND color_high >= color_low AND color_high < 1000000000000
                    AND scale(color_low) <= 12 AND scale(color_high) <= 12
                    AND color_unit IN ('lovibond','srm','ebc') AND length(color_basis) BETWEEN 1 AND 200 AND btrim(color_basis) <> ''))
        )""",
        """CREATE TABLE fermentable_flavor (
            revision_id text NOT NULL REFERENCES fermentable_revision(id) ON DELETE RESTRICT,
            position integer NOT NULL CHECK (position BETWEEN 1 AND 32),
            descriptor text NOT NULL CHECK (descriptor ~ '^[a-z][a-z0-9_-]{0,39}$'),
            PRIMARY KEY (revision_id, descriptor), UNIQUE (revision_id, position)
        )""",
        """CREATE TABLE fermentable_component (
            extract_revision_id text NOT NULL, extract_kind text NOT NULL CHECK (extract_kind IN ('dme','lme')),
            position integer NOT NULL CHECK (position BETWEEN 1 AND 100),
            grain_revision_id text NOT NULL, grain_kind text NOT NULL DEFAULT 'grain' CHECK (grain_kind = 'grain'),
            mass_fraction numeric NOT NULL CHECK (mass_fraction > 0 AND mass_fraction <= 1 AND scale(mass_fraction) <= 12),
            PRIMARY KEY (extract_revision_id, position), UNIQUE (extract_revision_id, grain_revision_id),
            FOREIGN KEY (extract_revision_id, extract_kind) REFERENCES fermentable_revision(id, kind) ON DELETE RESTRICT,
            FOREIGN KEY (grain_revision_id, grain_kind) REFERENCES fermentable_revision(id, kind) ON DELETE RESTRICT
        )""",
    ):
        op.execute(statement)
    application = context.config.attributes.get('application_role')
    if application is not None:
        role = op.get_bind().dialect.identifier_preparer.quote_identifier(application)
        op.execute(f'GRANT SELECT, INSERT ON TABLE fermentable_product, fermentable_revision, '
                   f'fermentable_flavor, fermentable_component TO {role}')


def downgrade() -> None:
    connection = op.get_bind()
    tables = ('fermentable_product', 'fermentable_revision', 'fermentable_flavor', 'fermentable_component')
    connection.execute(sa.text('LOCK TABLE ' + ', '.join(tables) + ' IN ACCESS EXCLUSIVE MODE'))
    if any(connection.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM {table})')).scalar_one() for table in tables):
        raise RuntimeError('Catalogue data exists; downgrade requires a reviewed data-preservation plan.')
    for table in reversed(tables):
        op.execute(f'DROP TABLE {table}')
