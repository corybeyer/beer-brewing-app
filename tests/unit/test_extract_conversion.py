"""C1/CV-01–CV-04: independently worked references and exact invariants."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest

from brewery_domain.extract_conversion import (
    ConversionInputError, FermentableYield, Mass, convert_fermentable,
)


D = Decimal


def supplied(potential='37', recovery='1', point='kettle'):
    return FermentableYield(D(potential), D(recovery), point, 'Explicit test assumption; not a product recommendation')


class ExtractConversionTests(unittest.TestCase):
    def test_brewers_friend_liquid_dry_reference_cf01(self):
        # https://www.brewersfriend.com/lme-dme-conversion-calculator/
        source = replace(supplied(), provenance='Brewers Friend LME/DME convention: 37 PPG liquid')
        target = replace(supplied('45'), provenance='Brewers Friend LME/DME convention: 45 PPG dry')
        result = convert_fermentable(Mass(D('3'), 'lb'), source, target, 'lb')
        self.assertEqual(result.amount, Fraction(37, 15))
        self.assertEqual(result.gravity_points_gallons, 111)
        self.assertEqual(result.calculation_version, 'gravity-equivalence/v1')
        self.assertEqual(result.source_yield, source)
        self.assertEqual(result.target_yield, target)

    def test_dry_to_grain_worked_reference_cf02(self):
        result = convert_fermentable(Mass(D('3'), 'lb'), supplied('45'), supplied('37', '.75'), 'lb')
        self.assertEqual(result.amount, Fraction(180, 37))
        self.assertEqual(result.gravity_points_gallons, 135)

    def test_foambyte_metric_references_cf03_cf04(self):
        # https://foambyte.com/calculators/grain-to-extract-conversion/
        # Reproduce its explicit convention, including unit recovery for extract.
        grain = supplied('36', '.75', 'fermenter')
        for potential, expected in [('42', Fraction(45, 14)), ('36', Fraction(15, 4))]:
            with self.subTest(target_potential=potential):
                result = convert_fermentable(Mass(D('5'), 'kg'), grain, supplied(potential, point='fermenter'), 'kg')
                self.assertEqual(result.amount, expected)

    def test_jays_chart_under_explicit_compatible_assumptions_cf05(self):
        # https://jaysbrewingblog.com/2011/11/17/lazy-chart-for-converting-dme-lme-grain/
        # Chart ratios do not state these potentials/efficiency; these are our inputs.
        grain = supplied('36', '.75')
        for potential, expected in [('36', Fraction(15, 2)), ('45', Fraction(6))]:
            self.assertEqual(convert_fermentable(Mass(D('10'), 'lb'), grain, supplied(potential), 'lb').amount, expected)

    def test_differing_defaults_are_distinct_results_not_averaged(self):
        result_42 = convert_fermentable(Mass(D('5'), 'kg'), supplied('36', '.75'), supplied('42'), 'kg')
        result_45 = convert_fermentable(Mass(D('5'), 'kg'), supplied('36', '.75'), supplied('45'), 'kg')
        self.assertEqual(result_42.amount, Fraction(45, 14))
        self.assertEqual(result_45.amount, 3)
        self.assertNotEqual(result_42.amount, result_45.amount)

    def test_identity_and_inverse_conserve_unrounded_gravity_contribution(self):
        mass = Mass(D('3.125'), 'lb')
        liquid, dry = supplied('37'), supplied('45')
        result = convert_fermentable(mass, liquid, dry, 'lb')
        # Feed exact recurring output back through the public domain interface.
        inverse = convert_fermentable(Mass(result.amount, result.unit), dry, liquid, 'lb')
        self.assertEqual(inverse.amount, Fraction(mass.amount))
        self.assertEqual(inverse.gravity_points_gallons, result.gravity_points_gallons)
        self.assertEqual(result.amount * Fraction(dry.potential_ppg), result.gravity_points_gallons)
        self.assertEqual(convert_fermentable(mass, liquid, liquid, 'lb').amount, Fraction(mass.amount))

    def test_metric_and_us_mass_inputs_describe_the_same_contribution(self):
        inputs = [Mass(D('1'), 'lb'), Mass(D('16'), 'oz'),
                  Mass(D('.45359237'), 'kg'), Mass(D('453.59237'), 'g')]
        for mass in inputs:
            for unit, expected in [('lb', Fraction(1)), ('oz', Fraction(16)),
                                   ('kg', Fraction(D('.45359237'))), ('g', Fraction(D('453.59237')))]:
                with self.subTest(mass=mass, output=unit):
                    result = convert_fermentable(mass, supplied(), supplied(), unit)
                    self.assertEqual(result.amount, expected)
                    self.assertEqual(result.gravity_points_gallons, 37)

    def test_lower_grain_recovery_needs_more_mass(self):
        source = supplied('45')
        low = convert_fermentable(Mass(D('3'), 'lb'), source, supplied('37', '.65'), 'lb')
        high = convert_fermentable(Mass(D('3'), 'lb'), source, supplied('37', '.80'), 'lb')
        self.assertGreater(low.amount, high.amount)
        self.assertEqual(low.gravity_points_gallons, high.gravity_points_gallons)

    def test_caller_decimal_context_does_not_change_results(self):
        mass = Mass(D('3.123456789012'), 'kg')
        source, target = supplied('44.123456'), supplied('36.123456', '.731234')
        expected = convert_fermentable(mass, source, target, 'oz')
        with localcontext() as context:
            context.prec = 1
            context.rounding = 'ROUND_DOWN'
            self.assertEqual(convert_fermentable(mass, source, target, 'oz'), expected)

    def test_inputs_and_result_are_immutable_and_retain_provenance(self):
        mass, source, target = Mass(D('3'), 'lb'), supplied('45'), supplied('37', '.75')
        result = convert_fermentable(mass, source, target, 'lb')
        self.assertIs(result.source_mass, mass)
        self.assertIs(result.source_yield, source)
        self.assertIs(result.target_yield, target)
        for value, field, replacement in [(mass, 'amount', D('4')), (source, 'potential_ppg', D('44')), (result, 'amount', Fraction(7))]:
            with self.assertRaises(FrozenInstanceError):
                setattr(value, field, replacement)

    def test_invalid_amounts_and_potentials_have_field_specific_errors(self):
        invalid = [None, True, 3, 0.1, '3', D('0'), D('-1'), D('NaN'), D('sNaN'), D('Infinity'), D('-Infinity')]
        for value in invalid:
            for field in ['source_mass.amount', 'source_yield.potential_ppg', 'target_yield.potential_ppg']:
                with self.subTest(value=value, field=field):
                    mass, source, target = Mass(D('3'), 'lb'), supplied(), supplied()
                    if field == 'source_mass.amount': mass = replace(mass, amount=value)
                    elif field.startswith('source_yield'): source = replace(source, potential_ppg=value)
                    else: target = replace(target, potential_ppg=value)
                    with self.assertRaises(ConversionInputError) as error:
                        convert_fermentable(mass, source, target, 'lb')
                    self.assertEqual(error.exception.path, field)

    def test_percentages_missing_recoveries_and_invalid_recoveries_are_rejected(self):
        for value in [None, True, 1, 0.75, D('0'), D('-1'), D('1.01'), D('75'), D('NaN'), D('Infinity')]:
            with self.subTest(value=value):
                with self.assertRaises(ConversionInputError) as error:
                    convert_fermentable(Mass(D('3'), 'lb'), supplied(), replace(supplied(), recovery_fraction=value), 'lb')
                self.assertEqual(error.exception.path, 'target_yield.recovery_fraction')

    def test_reference_points_and_provenance_cannot_be_inferred(self):
        invalid = [('comparison_point', None), ('comparison_point', 'mash'), ('comparison_point', 'fermenter'),
                   ('provenance', None), ('provenance', ''), ('provenance', ' ')]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ConversionInputError) as error:
                    convert_fermentable(Mass(D('3'), 'lb'), supplied(), replace(supplied(), **{field: value}), 'lb')
                self.assertEqual(error.exception.path, 'target_yield.' + field)

    def test_fluid_volumes_unknown_and_missing_mass_units_are_rejected(self):
        for value in [None, 'L', 'mL', 'US_fl_oz', 'US_gal', 'pounds', '', [], True]:
            for input_unit in (True, False):
                with self.subTest(unit=value, input_unit=input_unit):
                    with self.assertRaises(ConversionInputError) as error:
                        convert_fermentable(Mass(D('3'), value if input_unit else 'lb'), supplied(), supplied(), 'lb' if input_unit else value)
                    self.assertEqual(error.exception.path, 'source_mass.unit' if input_unit else 'target_unit')

    def test_numeric_bounds_prevent_extreme_rational_expansion(self):
        for value in [D('1e999999999'), D('1e-999999999'), D('1e13'), D('1.123456789012345678901234')]:
            with self.subTest(value=value):
                with self.assertRaises(ConversionInputError):
                    convert_fermentable(Mass(value, 'lb'), supplied(), supplied(), 'lb')
        for value in [Fraction(0), Fraction(-1), Fraction(1, 2**513), Fraction(2**513, 1)]:
            with self.assertRaises(ConversionInputError):
                convert_fermentable(Mass(value, 'lb'), supplied(), supplied(), 'lb')
        self.assertEqual(convert_fermentable(Mass(D('0.000000000001'), 'lb'), supplied(), supplied(), 'lb').amount,
                         Fraction(1, 10**12))

    def test_missing_typed_inputs_are_rejected_without_a_fallback(self):
        for mass, source, target, field in [(None, supplied(), supplied(), 'source_mass'),
                                           (Mass(D('3'), 'lb'), None, supplied(), 'source_yield'),
                                           (Mass(D('3'), 'lb'), supplied(), None, 'target_yield')]:
            with self.assertRaises(ConversionInputError) as error:
                convert_fermentable(mass, source, target, 'lb')
            self.assertEqual(error.exception.path, field)
