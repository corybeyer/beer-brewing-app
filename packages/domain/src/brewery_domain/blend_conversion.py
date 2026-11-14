"""Exact grain-blend gravity sizing using explicit, retained C1 assumptions."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Literal

from .extract_conversion import ConversionInputError, FermentableYield, Mass, MassUnit, convert_fermentable
from .fermentable_catalogue import CatalogRevision, validate_catalog_revision


@dataclass(frozen=True)
class BlendTarget:
    profile: CatalogRevision
    mass_fraction: Decimal
    yield_assumption: FermentableYield
    potential_override_note: str | None = None


@dataclass(frozen=True)
class BlendComponentAmount:
    revision_id: str
    amount: Fraction
    gravity_points_gallons: Fraction


@dataclass(frozen=True)
class BlendConversionResult:
    source_mass: Mass
    source_yield: FermentableYield
    targets: tuple[BlendTarget, ...]
    amount: Fraction
    unit: MassUnit
    components: tuple[BlendComponentAmount, ...]
    gravity_points_gallons: Fraction
    calculation_version: Literal['grain-blend-gravity/v1'] = 'grain-blend-gravity/v1'


class BlendInputError(ConversionInputError):
    """An explicit blend input is missing, unsupported, or inconsistent."""


def convert_grain_blend(source_mass: Mass, source_yield: FermentableYield,
                        targets: tuple[BlendTarget, ...], target_unit: MassUnit) -> BlendConversionResult:
    """Conserve estimated gravity with exact component masses and no recipe writes.

    Shares describe target grain mass, not gravity shares. Yields and recovery
    belong to the caller's declared comparison point. This calculation does not
    establish enzyme sufficiency, fermentability, flavor equivalence, or readiness.
    """
    if not isinstance(targets, tuple) or not 1 <= len(targets) <= 100:
        raise BlendInputError('targets', 'Supply one to 100 immutable grain targets.')
    shares, points_per_unit, seen = [], [], set()
    product_revisions = set()
    source_points = None
    for index, target in enumerate(targets):
        path = f'targets[{index}]'
        if not isinstance(target, BlendTarget):
            raise BlendInputError(path, 'Supply a grain profile, exact mass share, and explicit yield assumption.')
        if not isinstance(target.profile, CatalogRevision):
            raise BlendInputError(path + '.profile', 'Supply a complete immutable catalogue revision.')
        profile_issues = validate_catalog_revision(target.profile)
        if profile_issues:
            first = profile_issues[0]
            raise BlendInputError(path + '.profile.' + first.path, first.message)
        if target.profile.kind != 'grain':
            raise BlendInputError(path + '.profile.kind', 'Blend targets must be grain revisions.')
        if target.profile.revision_id in seen:
            raise BlendInputError(path + '.profile.revision_id', 'Use each grain revision only once.')
        seen.add(target.profile.revision_id)
        product_revision = (target.profile.product_id, target.profile.revision_number)
        if product_revision in product_revisions:
            raise BlendInputError(path + '.profile.revision_number', 'A product revision number identifies one catalogue revision.')
        product_revisions.add(product_revision)
        share = target.mass_fraction
        if not isinstance(share, Decimal) or not share.is_finite() or not 0 < share <= 1:
            raise BlendInputError(path + '.mass_fraction', 'Supply a finite positive Decimal mass share no greater than one.')
        parts = share.as_tuple()
        if len(parts.digits) > 24 or not -12 <= parts.exponent <= 12:
            raise BlendInputError(path + '.mass_fraction', 'Use at most 24 digits and 12 fractional places for mass shares.')
        note = target.potential_override_note
        if note is not None and (not isinstance(note, str) or not note.strip() or '\x00' in note or len(note) > 4000):
            raise BlendInputError(path + '.potential_override_note', 'Supply a nonblank potential override explanation up to 4000 characters.')
        try:
            conversion = convert_fermentable(source_mass, source_yield, target.yield_assumption, target_unit)
        except ConversionInputError as error:
            field = path + '.yield_assumption' + error.path[len('target_yield'):] if error.path.startswith('target_yield') else error.path
            raise BlendInputError(field, str(error)) from None
        if '\x00' in source_yield.provenance:
            raise BlendInputError('source_yield.provenance', 'Yield provenance cannot contain NUL.')
        if (target.profile.potential_ppg is None or target.profile.potential_ppg != target.yield_assumption.potential_ppg) and note is None:
            raise BlendInputError(path + '.potential_override_note', 'Explain a missing or overridden catalogue potential explicitly.')
        if '\x00' in target.yield_assumption.provenance:
            raise BlendInputError(path + '.yield_assumption.provenance', 'Yield provenance cannot contain NUL.')
        # A C1 conversion with one target mass unit as its source supplies the
        # exact gravity contribution per unit. No private C1 unit/yield helpers
        # or duplicate conversion constants are needed.
        unit_conversion = convert_fermentable(Mass(Decimal('1'), target_unit),
            target.yield_assumption, source_yield, source_mass.unit)
        source_points = conversion.gravity_points_gallons
        shares.append(Fraction(share))
        points_per_unit.append(unit_conversion.gravity_points_gallons)
    if sum(shares, Fraction()) != 1:
        raise BlendInputError('targets', 'Target grain mass shares must total exactly one.')
    weighted_points = sum((share * points for share, points in zip(shares, points_per_unit)), Fraction())
    amount = source_points / weighted_points
    components = tuple(BlendComponentAmount(target.profile.revision_id, amount * share,
                        amount * share * points)
                       for target, share, points in zip(targets, shares, points_per_unit))
    return BlendConversionResult(source_mass, source_yield, targets, amount, target_unit, components, source_points)
