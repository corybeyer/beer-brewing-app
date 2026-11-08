"""Exact gravity-contribution equivalence; no product matching or recipe writes.

Inputs supply potential, recovery and provenance explicitly. The comparison
point must match on both sides; equal gravity contribution implies equal
estimated gravity only at equal wort volume. See docs/plan/extract-conversion.md.
"""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Literal


MassUnit = Literal['g', 'kg', 'oz', 'lb']
ComparisonPoint = Literal['kettle', 'fermenter']
_POUNDS_PER_UNIT = {
    'lb': Fraction(1), 'oz': Fraction(1, 16),
    'kg': Fraction(100000000, 45359237), 'g': Fraction(100000, 45359237),
}


@dataclass(frozen=True)
class Mass:
    amount: Decimal | Fraction
    unit: MassUnit


@dataclass(frozen=True)
class FermentableYield:
    potential_ppg: Decimal
    recovery_fraction: Decimal
    comparison_point: ComparisonPoint
    provenance: str


@dataclass(frozen=True)
class ConversionResult:
    source_mass: Mass
    source_yield: FermentableYield
    target_yield: FermentableYield
    amount: Fraction
    unit: MassUnit
    gravity_points_gallons: Fraction
    calculation_version: Literal['gravity-equivalence/v1'] = 'gravity-equivalence/v1'


class ConversionInputError(ValueError):
    def __init__(self, path: str, message: str):
        self.path = path
        super().__init__(message)


def _positive_decimal(value, path):
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ConversionInputError(path, 'Supply a finite positive Decimal value.')
    digits = value.as_tuple()
    # Bound rational construction before expanding an extreme decimal exponent.
    if len(digits.digits) > 24 or not -12 <= digits.exponent <= 12 or value.adjusted() > 12:
        raise ConversionInputError(path, 'Use at most 24 digits, exponent -12 through 12, and magnitude below 10^13.')
    return Fraction(value)


def _mass_amount(value):
    # Computed masses can be chained without converting a recurring fraction to
    # a rounded Decimal. Transport adapters still parse explicit decimal text.
    if isinstance(value, Fraction):
        if value <= 0 or max(value.numerator.bit_length(), value.denominator.bit_length()) > 512:
            raise ConversionInputError('source_mass.amount', 'Supply a positive rational mass with numerator/denominator no larger than 512 bits.')
        return value
    return _positive_decimal(value, 'source_mass.amount')


def _yield(value, path):
    if not isinstance(value, FermentableYield):
        raise ConversionInputError(path, 'Supply an explicit fermentable yield.')
    potential = _positive_decimal(value.potential_ppg, path + '.potential_ppg')
    recovery = _positive_decimal(value.recovery_fraction, path + '.recovery_fraction')
    if recovery > 1:
        raise ConversionInputError(path + '.recovery_fraction', 'Recovery is a fraction above zero and no greater than one.')
    if value.comparison_point not in ('kettle', 'fermenter'):
        raise ConversionInputError(path + '.comparison_point', 'Choose kettle or fermenter as the comparison point.')
    if not isinstance(value.provenance, str) or not value.provenance.strip():
        raise ConversionInputError(path + '.provenance', 'Identify the product data, source convention, or explicit manual assumption.')
    return potential * recovery


def _unit(unit, path):
    if not isinstance(unit, str) or unit not in _POUNDS_PER_UNIT:
        raise ConversionInputError(path, 'Choose g, kg, oz, or lb; fluid volume is not ingredient mass.')
    return _POUNDS_PER_UNIT[unit]


def convert_fermentable(mass: Mass, source: FermentableYield,
                        target: FermentableYield, target_unit: MassUnit) -> ConversionResult:
    """Conserve estimated gravity points with exact, unrounded mass output.

    No potentials or recoveries are inferred, including for extracts. A caller
    using recovery 1 must identify that assumption in the supplied provenance.
    Product/catalogue adapters will own ingredient-specific input rules.
    """
    if not isinstance(mass, Mass):
        raise ConversionInputError('source_mass', 'Supply a mass with an explicit unit.')
    amount = _mass_amount(mass.amount)
    source_factor = _unit(mass.unit, 'source_mass.unit')
    target_factor = _unit(target_unit, 'target_unit')
    source_yield = _yield(source, 'source_yield')
    target_yield = _yield(target, 'target_yield')
    if source.comparison_point != target.comparison_point:
        raise ConversionInputError('target_yield.comparison_point', 'Both yields must describe the same comparison point.')
    points = amount * source_factor * source_yield
    return ConversionResult(mass, source, target, points / target_yield / target_factor,
                            target_unit, points)
