"""Deterministic exact grain-blend sizing; synthetic data is not a brew recommendation."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest

from brewery_domain.blend_conversion import BlendInputError, BlendTarget, convert_grain_blend
from brewery_domain.extract_conversion import FermentableYield, Mass, convert_fermentable
from tests.fixtures.catalogue_support import grain

D = Decimal


def target(revision='grain-r1', potential='37', share='1', recovery='.75'):
    profile = replace(grain(revision, revision), potential_ppg=D(potential))
    return BlendTarget(profile, D(share), FermentableYield(D(potential), D(recovery), 'kettle', 'Synthetic explicit yield and recovery'))


def source_yield():
    return FermentableYield(D('45'), D('1'), 'kettle', 'Synthetic DME potential and complete kettle recovery')


class BlendConversionTests(unittest.TestCase):
    def assert_invalid(self, path, targets, mass=Mass(D('3'), 'lb'), source=None, unit='lb'):
        with self.assertRaises(BlendInputError) as error:
            convert_grain_blend(mass, source_yield() if source is None else source, targets, unit)
        self.assertEqual(error.exception.path, path)

    def test_one_grain_matches_c1_and_preserves_complete_inputs(self):
        targets = (target(),)
        source = source_yield()
        mass = Mass(D('3'), 'lb')
        result = convert_grain_blend(mass, source, targets, 'lb')
        expected = convert_fermentable(mass, source, targets[0].yield_assumption, 'lb')
        self.assertEqual(result.amount, expected.amount)
        self.assertEqual(result.amount, Fraction(180, 37))
        self.assertEqual(result.components[0].amount, expected.amount)
        self.assertEqual(result.gravity_points_gallons, expected.gravity_points_gallons)
        self.assertIs(result.source_mass, mass)
        self.assertIs(result.source_yield, source)
        self.assertIs(result.targets, targets)
        self.assertEqual(result.calculation_version, 'grain-blend-gravity/v1')
        with self.assertRaises(FrozenInstanceError):
            result.amount = Fraction(5)

    def test_blend_uses_mass_shares_and_each_components_actual_yield_and_recovery(self):
        targets = (target('a', '36', '.75', '.8'), target('b', '40', '.25', '.6'))
        result = convert_grain_blend(Mass(D('3'), 'lb'), source_yield(), targets, 'lb')
        # .75 * 36 * .8 + .25 * 40 * .6 = 27.6 gravity units/lb.
        self.assertEqual(result.amount, Fraction(225, 46))
        self.assertEqual(tuple(item.amount for item in result.components), (Fraction(675, 184), Fraction(225, 184)))
        self.assertEqual(sum((item.amount for item in result.components), Fraction()), result.amount)
        self.assertEqual(sum((item.gravity_points_gallons for item in result.components), Fraction()), Fraction(135))
        self.assertEqual(result.gravity_points_gallons, Fraction(135))
        self.assertNotEqual(result.components[0].gravity_points_gallons / Fraction(135), Fraction(3, 4))

    def test_target_unit_conversions_are_exact_and_share_same_gravity(self):
        targets = (target('a', '36', '.6'), target('b', '40', '.4'))
        lb = convert_grain_blend(Mass(D('3'), 'lb'), source_yield(), targets, 'lb')
        oz = convert_grain_blend(Mass(D('48'), 'oz'), source_yield(), targets, 'oz')
        grams = convert_grain_blend(Mass(D('1360.77711'), 'g'), source_yield(), targets, 'g')
        kg = convert_grain_blend(Mass(D('1.36077711'), 'kg'), source_yield(), targets, 'kg')
        self.assertEqual(oz.amount, lb.amount * 16)
        self.assertEqual(grams.amount, kg.amount * 1000)
        self.assertEqual(grams.amount, lb.amount * Fraction(45359237, 100000))
        for result in (oz, grams, kg):
            self.assertEqual(result.gravity_points_gallons, lb.gravity_points_gallons)

    def test_exact_share_total_and_results_ignore_decimal_context(self):
        targets = (target('a', '36', '.1'), target('b', '37', '.2'), target('c', '38', '.7'))
        baseline = convert_grain_blend(Mass(D('3'), 'lb'), source_yield(), targets, 'lb')
        with localcontext() as context:
            context.prec = 1
            self.assertEqual(convert_grain_blend(Mass(D('3'), 'lb'), source_yield(), targets, 'lb'), baseline)
        self.assert_invalid('targets', targets[:-1])

    def test_missing_or_overridden_product_potential_requires_explanation(self):
        selected = target()
        unknown = replace(selected, profile=replace(selected.profile, potential_ppg=None, potential_status='unknown'))
        self.assert_invalid('targets[0].potential_override_note', (unknown,))
        changed = replace(selected, yield_assumption=replace(selected.yield_assumption, potential_ppg=D('38')))
        self.assert_invalid('targets[0].potential_override_note', (changed,))
        for item in (unknown, changed):
            result = convert_grain_blend(Mass(D('3'), 'lb'), source_yield(), (replace(item, potential_override_note='Explicit benchmark potential'),), 'lb')
            self.assertEqual(result.targets[0].potential_override_note, 'Explicit benchmark potential')

    def test_explicit_fermenter_assumptions_work_when_comparison_points_match(self):
        source = replace(source_yield(), recovery_fraction=D('.9'), comparison_point='fermenter')
        selected = target()
        selected = replace(selected, yield_assumption=replace(selected.yield_assumption, comparison_point='fermenter'))
        result = convert_grain_blend(Mass(D('3'), 'lb'), source, (selected,), 'lb')
        self.assertEqual(result.gravity_points_gallons, Fraction(243, 2))
        self.assertEqual(result.amount, Fraction(162, 37))

    def test_unknown_untyped_and_duplicate_targets_are_rejected(self):
        self.assert_invalid('targets', ())
        self.assert_invalid('targets', [target()])
        self.assert_invalid('targets[0]', (None,))
        self.assert_invalid('targets[0].profile', (replace(target(), profile=None),))
        self.assert_invalid('targets[1].profile.revision_id', (target(share='.5'), target(share='.5')))
        self.assert_invalid('targets', (target(),) * 101)

    def test_profile_must_be_valid_grain(self):
        selected = target()
        self.assert_invalid('targets[0].profile.kind', (replace(selected, profile=replace(selected.profile, kind='dme')),))
        self.assert_invalid('targets[0].profile.source_label', (replace(selected, profile=replace(selected.profile, source_label='')),))
        self.assert_invalid('targets[0].profile.flavor_tags', (replace(selected, profile=replace(selected.profile, flavor_tags=['malty'])),))

    def test_nonpositive_nonfinite_untyped_and_excessive_shares_are_rejected_before_fraction_expansion(self):
        for share in (True, 1, 1.0, '1', D('0'), D('-1'), D('2'), D('NaN'), D('sNaN'), D('Infinity'),
                      D('1e9999999'), D('1e-9999999'), D('0.1234567890123'), D('1.000000000000000000000000')):
            with self.subTest(share=share):
                self.assert_invalid('targets[0].mass_fraction', (replace(target(), mass_fraction=share),))

    def test_yield_recovery_reference_and_provenance_validation_reuses_c1(self):
        selected = target()
        for fields, suffix in (({'recovery_fraction': D('0')}, 'recovery_fraction'),
                               ({'recovery_fraction': D('1.1')}, 'recovery_fraction'),
                               ({'potential_ppg': D('NaN')}, 'potential_ppg'),
                               ({'comparison_point': 'fermenter'}, 'comparison_point'),
                               ({'provenance': ''}, 'provenance')):
            with self.subTest(fields=fields):
                self.assert_invalid('targets[0].yield_assumption.' + suffix,
                    (replace(selected, yield_assumption=replace(selected.yield_assumption, **fields)),))
        self.assert_invalid('targets[0].yield_assumption', (replace(selected, yield_assumption=None),))

    def test_source_and_units_keep_c1_error_paths(self):
        self.assert_invalid('source_mass.amount', (target(),), mass=Mass(D('0'), 'lb'))
        self.assert_invalid('source_mass.amount', (target(),), mass=Mass(Fraction(1, 2**600), 'lb'))
        self.assert_invalid('source_yield.provenance', (target(),), source=replace(source_yield(), provenance=''))
        self.assert_invalid('source_mass.unit', (target(),), mass=Mass(D('3'), 'L'))
        self.assert_invalid('target_unit', (target(),), unit='US_gal')

    def test_override_notes_are_nonblank_bounded_text(self):
        for note in ('', ' ', True, 'bad\x00note', 'x' * 4001):
            with self.subTest(note=type(note)):
                self.assert_invalid('targets[0].potential_override_note', (replace(target(), potential_override_note=note),))


    def test_rational_source_and_maximum_number_of_grains_remain_exact(self):
        targets = tuple(target('grain-' + str(index), '37', '.01') for index in range(100))
        result = convert_grain_blend(Mass(Fraction(3), 'lb'), source_yield(), targets, 'lb')
        self.assertEqual(result.amount, Fraction(180, 37))
        self.assertEqual(sum((item.amount for item in result.components), Fraction()), result.amount)
        self.assertEqual(sum((item.gravity_points_gallons for item in result.components), Fraction()), Fraction(135))

    def test_nul_in_assumption_provenance_is_rejected(self):
        self.assert_invalid('source_yield.provenance', (target(),), source=replace(source_yield(), provenance='bad\x00source'))
        selected = target()
        self.assert_invalid('targets[0].yield_assumption.provenance',
            (replace(selected, yield_assumption=replace(selected.yield_assumption, provenance='bad\x00target')),))


    def test_conflicting_product_revision_numbers_cannot_enter_the_same_blend(self):
        selected = target(share='.5')
        conflict = replace(selected, profile=replace(selected.profile, revision_id='another-id'))
        self.assert_invalid('targets[1].profile.revision_number', (selected, conflict))
