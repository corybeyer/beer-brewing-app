"""Immutable versioned conversion evidence with relational recipe ownership."""
from alembic import context, op
import sqlalchemy as sa


revision = '0004_conversion_proposals'
down_revision = '0003_fermentable_catalogue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE conversion_proposal (
        id text PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 128 AND id = btrim(id)),
        version_id text NOT NULL REFERENCES recipe_version(id) ON DELETE RESTRICT,
        original_edit_revision bigint NOT NULL CHECK (original_edit_revision > 0),
        created_at timestamptz NOT NULL CHECK (created_at > '-infinity'::timestamptz AND created_at < 'infinity'::timestamptz),
        format_version text NOT NULL CHECK (format_version = 'conversion-proposal/v1'),
        document jsonb NOT NULL CHECK (octet_length(document::text) <= 4194304),
        CHECK ((jsonb_typeof(document) = 'object'
            AND document->>'type' = 'ConversionProposal'
            AND document#>>'{fields,id}' = id
            AND document#>>'{fields,format_version}' = format_version
            AND document#>>'{fields,original,fields,draft,fields,plan,fields,version_id}' = version_id
            AND (document#>>'{fields,original,fields,edit_revision}')::bigint = original_edit_revision
            AND (document#>>'{fields,created_at,datetime}')::timestamptz = created_at) IS TRUE)
    )""")
    op.execute('CREATE INDEX conversion_proposal_version ON conversion_proposal (version_id, created_at, id)')
    application = context.config.attributes.get('application_role')
    if application is not None:
        role = op.get_bind().dialect.identifier_preparer.quote_identifier(application)
        op.execute(f'GRANT SELECT, INSERT ON TABLE conversion_proposal TO {role}')


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text('LOCK TABLE conversion_proposal IN ACCESS EXCLUSIVE MODE'))
    if connection.execute(sa.text('SELECT EXISTS (SELECT 1 FROM conversion_proposal)')).scalar_one():
        raise RuntimeError('Proposal data exists; downgrade requires a reviewed data-preservation plan.')
    op.execute('DROP TABLE conversion_proposal')
