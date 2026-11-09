"""Closed historical document codec; never instantiate caller-named Python types."""
from dataclasses import fields
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import re

from brewery_domain.conversion_proposals import ConversionProposal, IngredientConversion, capture_proposal
from brewery_domain.extract_conversion import ConversionResult, FermentableYield, Mass
from brewery_domain.fermentable_catalogue import CatalogRevision, GrainComponent, IngredientColor
from brewery_domain.recipe_plan import Addition, Ingredient, RecipePlan, Step
from brewery_domain.recipes import RecipeDraft, StoredDraft


MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
_TYPES = {kind.__name__: kind for kind in (
    ConversionProposal, IngredientConversion, ConversionResult, FermentableYield, Mass,
    CatalogRevision, GrainComponent, IngredientColor, Addition, Ingredient, RecipePlan,
    Step, RecipeDraft, StoredDraft,
)}
_DECIMAL = re.compile(r'-?[0-9]{1,24}(?:\.[0-9]{1,24})?(?:[eE][+-]?[0-9]{1,2})?\Z')
_INTEGER = re.compile(r'-?(?:0|[1-9][0-9]{0,154})\Z')


def _size(document):
    try:
        size = len(json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8'))
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise ValueError('Unsupported proposal document structure or text.') from None
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError('Proposal document exceeds its size limit.')


def encode_proposal(value: ConversionProposal) -> dict:
    capture_proposal(value)
    count = 0

    def encode(item, depth=0):
        nonlocal count
        count += 1
        if depth > 64 or count > 100000:
            raise ValueError('Proposal document exceeds its structural limits.')
        if type(item) in (type(None), bool, int, str):
            if isinstance(item, str) and '\x00' in item:
                raise ValueError('Proposal text cannot contain NUL.')
            return item
        if type(item) is Decimal:
            return {'decimal': str(item)}
        if type(item) is Fraction:
            return {'fraction': [str(item.numerator), str(item.denominator)]}
        if type(item) is datetime:
            return {'datetime': item.astimezone(timezone.utc).isoformat()}
        if type(item) is tuple:
            return [encode(child, depth + 1) for child in item]
        kind = _TYPES.get(type(item).__name__)
        if kind is not type(item):
            raise ValueError('Unsupported proposal document value.')
        return {'type': kind.__name__, 'fields': {field.name: encode(getattr(item, field.name), depth + 1)
                                                 for field in fields(kind)}}

    document = encode(value)
    _size(document)
    if decode_proposal(document) != value:
        raise ValueError('Proposal document cannot retain the exact input value.')
    return document


def decode_proposal(document: dict) -> ConversionProposal:
    _size(document)
    count = 0

    def decode(item, depth=0):
        nonlocal count
        count += 1
        if depth > 64 or count > 100000:
            raise ValueError('Proposal document exceeds its structural limits.')
        if type(item) in (type(None), bool, int, str):
            if isinstance(item, str) and '\x00' in item:
                raise ValueError('Proposal text cannot contain NUL.')
            return item
        if type(item) is list:
            return tuple(decode(child, depth + 1) for child in item)
        if type(item) is not dict:
            raise ValueError('Unsupported proposal document value.')
        if set(item) == {'decimal'}:
            raw = item['decimal']
            if not isinstance(raw, str) or not _DECIMAL.fullmatch(raw):
                raise ValueError('Unsupported decimal representation.')
            try:
                return Decimal(raw)
            except InvalidOperation:
                raise ValueError('Invalid decimal representation.') from None
        if set(item) == {'fraction'}:
            raw = item['fraction']
            if (not isinstance(raw, list) or len(raw) != 2
                    or any(not isinstance(part, str) or not _INTEGER.fullmatch(part) for part in raw)):
                raise ValueError('Unsupported rational representation.')
            numerator, denominator = (int(part) for part in raw)
            if denominator <= 0 or max(numerator.bit_length(), denominator.bit_length()) > 512:
                raise ValueError('Invalid or excessive rational representation.')
            return Fraction(numerator, denominator)
        if set(item) == {'datetime'}:
            if not isinstance(item['datetime'], str) or len(item['datetime']) > 64:
                raise ValueError('Unsupported timestamp representation.')
            return datetime.fromisoformat(item['datetime'])
        if set(item) != {'type', 'fields'} or not isinstance(item['type'], str):
            raise ValueError('Unknown proposal document tag.')
        kind = _TYPES.get(item['type'])
        if kind is None or type(item['fields']) is not dict or set(item['fields']) != {field.name for field in fields(kind)}:
            raise ValueError('Unknown proposal type or fields.')
        return kind(**{key: decode(child, depth + 1) for key, child in item['fields'].items()})

    value = decode(document)
    try:
        return capture_proposal(value)
    except (AttributeError, TypeError, KeyError):
        raise ValueError('Malformed proposal field types.') from None
