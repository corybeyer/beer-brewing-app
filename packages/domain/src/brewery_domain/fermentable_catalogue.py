"""Immutable sourced fermentable profiles; no transport, database, or matching."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
import re
from typing import Protocol
from ipaddress import IPv6Address


@dataclass(frozen=True)
class IngredientColor:
    low: Decimal
    high: Decimal
    unit: str
    basis: str


@dataclass(frozen=True)
class GrainComponent:
    grain_revision_id: str
    mass_fraction: Decimal


@dataclass(frozen=True)
class CatalogRevision:
    product_id: str
    revision_id: str
    revision_number: int
    kind: str
    name: str
    source_label: str
    source_retrieved_at: datetime
    source_url: str | None = None
    manufacturer: str | None = None
    potential_ppg: Decimal | None = None
    potential_status: str = 'unknown'
    potential_note: str | None = None
    color: IngredientColor | None = None
    flavor_notes: str | None = None
    flavor_tags: tuple[str, ...] = ()
    composition_status: str = 'unknown'
    composition_note: str | None = None
    components: tuple[GrainComponent, ...] = ()


@dataclass(frozen=True)
class CatalogIssue:
    code: str
    path: str
    message: str


class InvalidCatalogRevision(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__('Catalogue revision validation failed.')


class CatalogConflict(ValueError):
    """The revision already exists or a stable product kind would change."""


class CatalogUnavailable(RuntimeError):
    """The catalogue operation failed without exposing adapter details."""


class FermentableCatalog(Protocol):
    def append(self, revision: CatalogRevision) -> CatalogRevision: ...
    def load(self, revision_id: str) -> CatalogRevision | None: ...


def _valid_source_url(value: str) -> bool:
    """Validate provenance text without importing a network/transport module."""
    if any(character.isspace() for character in value):
        return False
    matched = re.fullmatch(r'https?://([^/?#]+)(?:[/?#].*)?', value, re.IGNORECASE)
    if not matched:
        return False
    authority = matched.group(1)
    if '@' in authority:
        return False
    if authority.startswith('['):
        host = re.fullmatch(r'\[([^\]]+)\](?::([0-9]{1,5}))?', authority)
        if not host:
            return False
        try:
            IPv6Address(host.group(1))
        except ValueError:
            return False
    else:
        host = re.fullmatch(r'([^:]+)(?::([0-9]{1,5}))?', authority)
        if (not host or len(host.group(1)) > 253 or any(
                not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                for label in host.group(1).split('.'))):
            return False
    return host.group(2) is None or 1 <= int(host.group(2)) <= 65535


def validate_catalog_revision(value: CatalogRevision) -> tuple[CatalogIssue, ...]:
    issues = []

    def issue(code, path, message):
        issues.append(CatalogIssue(code, path, message))

    def text(item, path, limit, optional=False, identifier=False):
        if optional and item is None:
            return True
        if (not isinstance(item, str) or not item.strip() or len(item) > limit or '\x00' in item
                or identifier and item.strip() != item):
            issue('invalid_text', path, f'Supply nonblank text up to {limit} characters without NUL or identifier padding.')
            return False
        return True

    def number(item, path, zero=False):
        if not isinstance(item, Decimal) or not item.is_finite() or item < 0 or not zero and item == 0:
            issue('invalid_number', path, 'Supply a finite decimal in the permitted positive range.')
            return False
        parts = item.as_tuple()
        if len(parts.digits) > 24 or not -12 <= parts.exponent <= 12 or item.adjusted() > 11:
            issue('invalid_precision', path, 'Use at most 24 digits, 12 fractional places, and fewer than 10^12 units.')
            return False
        return True

    text(value.product_id, 'product_id', 128, identifier=True)
    text(value.revision_id, 'revision_id', 128, identifier=True)
    if type(value.revision_number) is not int or not 1 <= value.revision_number <= 2147483647:
        issue('invalid_revision', 'revision_number', 'Use a positive revision number.')
    if value.kind not in ('grain', 'dme', 'lme'):
        issue('invalid_kind', 'kind', 'Choose grain, dme, or lme.')
    for field, limit, optional in [('name', 200, False), ('source_label', 200, False),
                                   ('manufacturer', 200, True), ('potential_note', 4000, True),
                                   ('flavor_notes', 4000, True), ('composition_note', 4000, True)]:
        text(getattr(value, field), field, limit, optional=optional)
    if not isinstance(value.source_retrieved_at, datetime) or value.source_retrieved_at.utcoffset() is None:
        issue('invalid_timestamp', 'source_retrieved_at', 'Supply a timezone-aware source retrieval time.')
    if value.source_url is not None and text(value.source_url, 'source_url', 2048):
        if not _valid_source_url(value.source_url):
            issue('invalid_source_url', 'source_url', 'Use an HTTP(S) source URL without credentials or whitespace.')
    for field in ('potential_status', 'composition_status'):
        if getattr(value, field) not in ('unknown', 'manufacturer', 'manual_assumption'):
            issue('invalid_status', field, 'Choose unknown, manufacturer, or manual_assumption.')
    if value.potential_ppg is not None:
        number(value.potential_ppg, 'potential_ppg')
    if (value.potential_status == 'unknown') != (value.potential_ppg is None):
        issue('missing_provenance', 'potential_status', 'Unknown potential stays absent; supplied potential needs a provenance status.')
    if value.potential_status == 'manual_assumption' and not value.potential_note:
        issue('missing_assumption', 'potential_note', 'Explain an assumed potential.')
    if 'manufacturer' in (value.potential_status, value.composition_status) and (not value.source_url or not value.manufacturer):
        issue('missing_source', 'source_url', 'Manufacturer-reported values need a manufacturer and source URL.')
    if value.color is not None:
        if not isinstance(value.color, IngredientColor):
            issue('invalid_color', 'color', 'Supply a color range with its unit and measurement basis.')
        else:
            low = number(value.color.low, 'color.low', zero=True)
            high = number(value.color.high, 'color.high', zero=True)
            if low and high and value.color.low > value.color.high:
                issue('invalid_color_range', 'color.high', 'Color high must not be below color low.')
            if value.color.unit not in ('lovibond', 'srm', 'ebc'):
                issue('invalid_color_unit', 'color.unit', 'Choose lovibond, srm, or ebc.')
            text(value.color.basis, 'color.basis', 200)
    tags = value.flavor_tags if isinstance(value.flavor_tags, tuple) else ()
    if not isinstance(value.flavor_tags, tuple) or len(tags) > 32:
        issue('invalid_tags', 'flavor_tags', 'Supply up to 32 ordered descriptor tags.')
    seen = set()
    for index, tag in enumerate(tags):
        if not isinstance(tag, str) or not re.fullmatch('[a-z][a-z0-9_-]{0,39}', tag) or tag in seen:
            issue('invalid_tag', f'flavor_tags[{index}]', 'Use unique lowercase descriptor tags up to 40 characters.')
        if isinstance(tag, str):
            seen.add(tag)
    components = value.components if isinstance(value.components, tuple) else ()
    if not isinstance(value.components, tuple) or len(components) > 100:
        issue('invalid_components', 'components', 'Supply up to 100 complete grain components.')
    if value.kind == 'grain' and (value.composition_status != 'unknown' or components):
        issue('grain_composition', 'components', 'Grain revisions do not contain extract grain bills.')
    if (value.composition_status == 'unknown') != (len(components) == 0):
        issue('composition_status', 'composition_status', 'Unknown composition has no components; a known/assumed bill must be complete.')
    if value.composition_status == 'manual_assumption' and not value.composition_note:
        issue('missing_assumption', 'composition_note', 'Explain an assumed grain bill.')
    total = Fraction()
    seen = set()
    valid = True
    for index, item in enumerate(components):
        path = f'components[{index}]'
        if not isinstance(item, GrainComponent):
            issue('invalid_component', path, 'Supply a grain revision and exact mass fraction.')
            valid = False
            continue
        if text(item.grain_revision_id, path + '.grain_revision_id', 128, identifier=True):
            if item.grain_revision_id in seen:
                issue('duplicate_component', path + '.grain_revision_id', 'Use each grain revision only once.')
            seen.add(item.grain_revision_id)
        if number(item.mass_fraction, path + '.mass_fraction'):
            if item.mass_fraction > 1:
                issue('invalid_fraction', path + '.mass_fraction', 'A component fraction cannot exceed one.')
            total += Fraction(item.mass_fraction)
        else:
            valid = False
    if components and valid and total != 1:
        issue('incomplete_composition', 'components', 'Grain mass fractions must total exactly one.')
    return tuple(issues)
