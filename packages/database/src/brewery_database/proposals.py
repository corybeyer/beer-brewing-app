"""Append-only exact snapshots under the recipe writer's shared parent lock."""
from functools import wraps
from datetime import timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from brewery_domain.conversion_proposals import (
    ConversionProposal, ConversionProposalConflict, ConversionProposalUnavailable,
    InvalidConversionProposal, StaleConversionProposal, capture_proposal, require_current_proposal,
)
from brewery_domain.fermentable_catalogue import CatalogUnavailable
from brewery_domain.recipe_plan import PlanIssue

from .catalogue import _read_revision
from .proposal_document import decode_proposal, encode_proposal
from .recipes import _stored, _version


_metadata = sa.MetaData()
_proposal = sa.Table('conversion_proposal', _metadata,
    sa.Column('id', sa.Text, primary_key=True), sa.Column('version_id', sa.Text),
    sa.Column('original_edit_revision', sa.BigInteger), sa.Column('created_at', sa.DateTime(timezone=True)),
    sa.Column('format_version', sa.Text), sa.Column('document', JSONB))


def _available(operation):
    @wraps(operation)
    def wrapped(*args, **options):
        try:
            return operation(*args, **options)
        except (InvalidConversionProposal, StaleConversionProposal, ConversionProposalConflict):
            raise
        except (SQLAlchemyError, CatalogUnavailable, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise ConversionProposalUnavailable('Conversion proposal storage is unavailable.') from None
    return wrapped


class PostgresConversionProposalStore:
    def __init__(self, engine):
        self.engine = engine

    @_available
    def append(self, value: ConversionProposal) -> ConversionProposal:
        capture_proposal(value)
        try:
            if len(value.id) > 128:
                raise ValueError('Proposal identifiers permit at most 128 characters.')
            document = encode_proposal(value)
        except (ValueError, TypeError, OverflowError, RecursionError):
            raise InvalidConversionProposal((PlanIssue('invalid_document', 'document',
                'Supply a supported, bounded proposal snapshot without NUL.'),)) from None
        try:
            with self.engine.begin() as connection:
                # The recipe adapter saves under FOR UPDATE on this same row.
                row = connection.execute(sa.select(_version).where(_version.c.id == value.original.draft.plan.version_id)
                                         .with_for_update(read=True)).mappings().one_or_none()
                current = _stored(connection, row) if row is not None and row['status'] == 'draft' else None
                require_current_proposal(value, current)
                for index, retained in enumerate(value.catalogue):
                    if _read_revision(connection, retained.revision_id) != retained:
                        raise InvalidConversionProposal((PlanIssue('catalogue_mismatch', f'catalogue[{index}]',
                            'Retain the authoritative stored catalogue revision.'),))
                connection.execute(_proposal.insert().values(id=value.id,
                    version_id=value.original.draft.plan.version_id,
                    original_edit_revision=value.original.edit_revision,
                    created_at=value.created_at.astimezone(timezone.utc), format_version=value.format_version, document=document))
            return value
        except IntegrityError as error:
            if getattr(error.orig, 'sqlstate', None) == '23505':
                raise ConversionProposalConflict('That immutable proposal identifier already exists.') from None
            raise

    @_available
    def load(self, proposal_id: str) -> ConversionProposal | None:
        with self.engine.connect() as connection:
            row = connection.execute(sa.select(_proposal).where(_proposal.c.id == proposal_id)).mappings().one_or_none()
            if row is None:
                return None
            try:
                value = decode_proposal(row['document'])
                if (value.id != row['id'] or value.original.draft.plan.version_id != row['version_id']
                        or value.original.edit_revision != row['original_edit_revision']
                        or value.created_at != row['created_at'] or value.format_version != row['format_version']):
                    raise ValueError('Stored proposal headers differ from their snapshot.')
            except (InvalidConversionProposal, ValueError, TypeError, KeyError, OverflowError, RecursionError):
                raise ConversionProposalUnavailable('Stored conversion proposal failed validation.') from None
            return value
