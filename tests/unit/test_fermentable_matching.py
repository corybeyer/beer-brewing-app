"""Synthetic evidence for C3 ranking; no manufacturer catalogue or recipe writes."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest

from brewery_domain.fermentable_catalogue import GrainComponent, IngredientColor
from brewery_domain.fermentable_matching import MatchingInputError, rank_grain_matches
from tests.fixtures.catalogue_support import extract, grain


D = Decimal


def unknown_source(**changes):
    value = replace(extract(), composition_status='unknown', components=(), composition_note=None)
    return replace(value, **changes)


def reasons(value):
    return {item.code for item in value.review}


class GrainMatchingTests(unittest.TestCase):
    def grains(self):
        return grain(), grain('grain-r2', 'second-grain')

    def test_reported_composition_precedes_optional_variations_and_preserves_attribution(self):
        source = replace(extract(), composition_status='manufacturer', manufacturer='Synthetic supplier',
                         source_url='https://example.test/synthetic-sheet', composition_note=None)
        grains = (*self.grains(), replace(grain('variation', 'variation-product'), flavor_tags=('malty', 'toasty', 'bread')))
        result = rank_grain_matches(source, grains, include_variations=True)
        first = result.options[0]
        self.assertEqual(first.relation, 'manufacturer_composition')
        self.assertEqual(tuple(item.mass_fraction for item in first.components), (D('.9'), D('.1')))
        self.assertEqual(tuple(item.revision for item in first.components), self.grains())
        self.assertIs(result.source, source)
        self.assertEqual(result.source.source_url, 'https://example.test/synthetic-sheet')
        self.assertTrue(all(item.relation in ('variation', 'unranked_variation') for item in result.options[1:]))

    def test_assumed_composition_has_its_own_label_and_explanation(self):
        result = rank_grain_matches(extract(), self.grains())
        self.assertEqual(len(result.options), 1)
        self.assertEqual(result.options[0].relation, 'assumed_composition')
        self.assertIn('source_composition_assumed', reasons(result))
        self.assertEqual(result.source.composition_note, 'Illustrative grain bill.')

    def test_unknown_dark_extract_never_invents_a_complete_grain_bill(self):
        source = unknown_source(color=IngredientColor(D('100'), D('200'), 'srm', 'Extract at source concentration'))
        result = rank_grain_matches(source, self.grains(), include_variations=True)
        self.assertIn('source_composition_unknown', reasons(result))
        self.assertTrue(all(item.relation in ('variation', 'unranked_variation') for item in result.options))
        self.assertEqual(rank_grain_matches(source, self.grains()).options, ())

    def test_missing_composition_reference_does_not_downgrade_to_an_exact_match(self):
        result = rank_grain_matches(extract(), self.grains()[:1], include_variations=True)
        self.assertIn('composition_grain_missing', reasons(result))
        self.assertEqual(result.review[-1].code, 'whole_recipe_review')
        self.assertFalse(any(item.relation.endswith('composition') for item in result.options))
        self.assertIn('grain-r2', {item.revision_id for item in result.review})

    def test_variation_order_is_independent_of_input_order(self):
        source = unknown_source()
        grains = (replace(grain('a', 'pa'), flavor_tags=('malty',)),
                  replace(grain('b', 'pb'), flavor_tags=('toasty',)),
                  replace(grain('c', 'pc'), flavor_tags=('malty', 'toasty')))
        first = rank_grain_matches(source, grains, True)
        second = rank_grain_matches(source, grains[::-1], True)
        self.assertEqual(first, second)
        self.assertEqual(tuple(item.components[0].revision.revision_id for item in first.options), ('c', 'a', 'b'))

    def test_jaccard_similarity_retains_exact_shared_tag_evidence(self):
        source = unknown_source()
        target = replace(grain(), flavor_tags=('malty', 'bread'))
        option = rank_grain_matches(source, (target,), True).options[0]
        self.assertEqual(option.tag_similarity, Fraction(1, 3))
        self.assertEqual(option.shared_flavor_tags, ('malty',))
        self.assertEqual(option.components[0].revision.flavor_tags, ('malty', 'bread'))

    def test_missing_descriptor_data_is_absent_not_a_perfect_match(self):
        source = unknown_source(flavor_tags=(), color=None)
        target = replace(grain(), flavor_tags=(), color=None)
        result = rank_grain_matches(source, (target,), True)
        option = result.options[0]
        self.assertIsNone(option.tag_similarity)
        self.assertIsNone(option.color_gap)
        self.assertEqual(option.relation, 'unranked_variation')
        self.assertIn('source_flavor_tags_missing', reasons(result))
        self.assertIn('no_similarity_evidence', reasons(option))

    def test_no_overlap_without_comparable_color_is_explicitly_unranked(self):
        source = unknown_source(color=None)
        target = replace(grain(), flavor_tags=('smoky',), color=None)
        option = rank_grain_matches(source, (target,), True).options[0]
        self.assertEqual(option.tag_similarity, Fraction(0))
        self.assertEqual(option.relation, 'unranked_variation')

    def test_usable_variations_precede_unranked_options(self):
        source = unknown_source(color=None)
        unranked = replace(grain('a', 'pa'), flavor_tags=('smoky',), color=None)
        ranked = replace(grain('z', 'pz'), flavor_tags=('malty',), color=None)
        result = rank_grain_matches(source, (unranked, ranked), True)
        self.assertEqual(tuple(item.relation for item in result.options), ('variation', 'unranked_variation'))

    def test_color_range_gap_is_exact_without_midpoint_rounding(self):
        source = unknown_source(flavor_tags=(), color=IngredientColor(D('2.123456789012'), D('3'), 'ebc', 'Same explicit test basis'))
        target = replace(grain(), flavor_tags=(), color=IngredientColor(D('3.123456789012'), D('5'), 'ebc', 'Same explicit test basis'))
        with localcontext() as context:
            context.prec = 1
            option = rank_grain_matches(source, (target,), True).options[0]
        self.assertEqual(option.color_gap, Fraction(D('.123456789012')))
        self.assertEqual(option.relation, 'variation')

    def test_overlapping_ranges_have_zero_gap_but_do_not_establish_equivalence(self):
        source = unknown_source(color=IngredientColor(D('2'), D('4'), 'lovibond', 'Test basis'))
        target = replace(grain(), color=IngredientColor(D('3'), D('5'), 'lovibond', 'Test basis'))
        result = rank_grain_matches(source, (target,), True)
        self.assertEqual(result.options[0].color_gap, Fraction(0))
        self.assertIn('whole_recipe_review', reasons(result))
        self.assertEqual(result.options[0].relation, 'variation')

    def test_different_color_units_or_bases_are_never_compared(self):
        source = unknown_source(color=IngredientColor(D('2'), D('3'), 'lovibond', 'Dry malt'))
        for color in (IngredientColor(D('2'), D('3'), 'srm', 'Dry malt'),
                      IngredientColor(D('2'), D('3'), 'lovibond', 'Extract at 8 percent')):
            with self.subTest(color=color):
                target = replace(grain(), color=color)
                option = rank_grain_matches(source, (target,), True).options[0]
                self.assertIsNone(option.color_gap)
                self.assertIn('color_basis_or_unit_differs', reasons(option))

    def test_color_breaks_equal_tag_scores_then_revision_id_breaks_equal_evidence(self):
        source = unknown_source()
        grains = (replace(grain('far', 'pf'), color=IngredientColor(D('10'), D('11'), 'lovibond', 'Malt as supplied')),
                  grain('b', 'pb'), grain('a', 'pa'))
        result = rank_grain_matches(source, grains, True)
        self.assertEqual(tuple(item.components[0].revision.revision_id for item in result.options), ('a', 'b', 'far'))

    def test_missing_potential_stays_missing_and_recovery_is_always_required(self):
        source = unknown_source(potential_ppg=None, potential_status='unknown', potential_note=None)
        target = replace(grain(), potential_ppg=None, potential_status='unknown', potential_note=None)
        result = rank_grain_matches(source, (target,), True)
        self.assertIsNone(result.source.potential_ppg)
        self.assertIsNone(result.options[0].components[0].revision.potential_ppg)
        self.assertIn('source_potential_required', reasons(result))
        self.assertIn('grain_potential_required', reasons(result.options[0]))
        self.assertTrue({'recovery_required', 'mash_feasibility_review', 'whole_recipe_review'} <= reasons(result))

    def test_assumed_potential_is_distinct_from_reported_potential(self):
        result = rank_grain_matches(unknown_source(), (grain(),), True)
        self.assertIn('source_potential_assumed', reasons(result))
        self.assertIn('grain_potential_assumed', reasons(result.options[0]))

    def test_complete_single_grain_bill_is_not_duplicated_as_a_variation(self):
        source = replace(extract(), components=(GrainComponent('grain-r1', D('1')),))
        result = rank_grain_matches(source, (grain(),), True)
        self.assertEqual(len(result.options), 1)
        self.assertEqual(result.options[0].relation, 'assumed_composition')

    def test_source_and_candidates_are_immutable_snapshots(self):
        result = rank_grain_matches(extract(), self.grains())
        with self.assertRaises(FrozenInstanceError):
            result.options[0].components[0].revision.name = 'Changed'
        with self.assertRaises(FrozenInstanceError):
            result.ranking_version = 'new'
        later = replace(self.grains()[0], revision_id='later', revision_number=2, name='Later')
        self.assertNotEqual(result.options[0].components[0].revision.name, later.name)

    def test_rejects_non_extract_source_non_grain_candidates_and_mutable_collections(self):
        for source, candidates, include in ((grain(), (), False), (extract(), (extract(),), True),
                                             (extract(), list(self.grains()), True), (extract(), self.grains(), 1),
                                             (None, self.grains(), True), (extract(), (None,), True)):
            with self.subTest(source=type(source)), self.assertRaises(MatchingInputError):
                rank_grain_matches(source, candidates, include)

    def test_rejects_duplicate_or_conflicting_profile_identities(self):
        for candidates in ((grain(), grain()),
                           (grain(), replace(grain(), revision_id='duplicate-number')),
                           (replace(grain(), product_id='extract'),)):
            with self.subTest(candidates=candidates), self.assertRaises(MatchingInputError):
                rank_grain_matches(extract(), candidates, True)

    def test_rejects_invalid_catalogue_values_instead_of_silently_ignoring_them(self):
        for target in (replace(grain(), potential_ppg=D('NaN')),
                       replace(grain(), flavor_tags=('Not A Tag',)),
                       replace(grain(), color=IngredientColor(D('5'), D('2'), 'ebc', 'basis'))):
            with self.subTest(target=target), self.assertRaises(MatchingInputError):
                rank_grain_matches(extract(), (target,), True)

    def test_empty_catalogue_and_excessive_inputs_are_explicit(self):
        result = rank_grain_matches(extract(), (), True)
        self.assertEqual(result.options, ())
        self.assertIn('composition_grain_missing', reasons(result))
        with self.assertRaises(MatchingInputError) as error:
            rank_grain_matches(extract(), (grain(),) * 1001, True)
        self.assertEqual(error.exception.path, 'grains')
