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
from .recipes import (
    DraftConflict, DraftNotFound, InvalidDraft, _addition, _dependency, _ingredient, _step,
    _stored, _validate, _version, _write_plan,
)


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
        except (InvalidConversionProposal, StaleConversionProposal, ConversionProposalConflict,
                DraftConflict, DraftNotFound, InvalidDraft):
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

    @_available
    def apply(self, proposal_id: str, expected_revision: int):
        """Apply once under the same parent lock used by every recipe writer."""
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('Expected edit revision must be positive.')
        with self.engine.begin() as connection:
            row = connection.execute(sa.select(_version).where(_version.c.id ==
                sa.select(_proposal.c.version_id).where(_proposal.c.id == proposal_id).scalar_subquery())
                .with_for_update()).mappings().one_or_none()
            if row is None:
                raise DraftNotFound('The proposal or its recipe draft does not exist.')
            if row['status'] != 'draft' or row['edit_revision'] != expected_revision:
                raise DraftConflict('The draft changed; review the latest saved version before applying.')
            current = _stored(connection, row)
            retained = connection.execute(sa.select(_proposal).where(
                _proposal.c.id == proposal_id, _proposal.c.version_id == row['id'])).mappings().one_or_none()
            if retained is None:
                raise DraftNotFound('The proposal does not exist for this recipe draft.')
            try:
                proposal = decode_proposal(retained['document'])
                require_current_proposal(proposal, current)
                if (proposal.id != retained['id'] or proposal.original.edit_revision != retained['original_edit_revision']
                        or proposal.created_at != retained['created_at'] or proposal.format_version != retained['format_version']):
                    raise ValueError('Stored proposal headers differ from their snapshot.')
            except StaleConversionProposal:
                raise DraftConflict('The original draft changed; review the latest version before applying.') from None
            except (InvalidConversionProposal, ValueError, TypeError, KeyError, OverflowError, RecursionError):
                raise ConversionProposalUnavailable('Stored conversion proposal failed validation.') from None
            _validate(proposal.proposed)
            updated = connection.execute(_version.update().where(_version.c.id == row['id']).values(
                name=proposal.proposed.name, description=proposal.proposed.description,
                edit_revision=expected_revision + 1, updated_at=sa.func.clock_timestamp(),
            ).returning(_version)).mappings().one()
            for table in (_addition, _dependency, _step, _ingredient):
                connection.execute(table.delete().where(table.c.version_id == row['id']))
            _write_plan(connection, proposal.proposed.plan)
            return _stored(connection, updated)
