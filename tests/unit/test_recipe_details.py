"""Draft metadata and volume targets stay bounded, optional, and exact."""
from decimal import Decimal
import unittest

from brewery_domain.recipe_details import RecipeDetails, VolumeTarget, normalize_details, validate_details


class RecipeDetailsTests(unittest.TestCase):
    def test_empty_details_are_valid_and_preserve_absence(self):
        self.assertEqual(validate_details(RecipeDetails()), ())

    def test_normalization_trims_tag_edges_preserving_order_and_display_case(self):
        details = normalize_details(RecipeDetails(tags=(' Pale Ale ', 'Citrus')))
        self.assertEqual(details.tags, ('Pale Ale', 'Citrus'))
        self.assertEqual(validate_details(details), ())

    def test_duplicate_tags_ignore_case_after_normalization(self):
        details = normalize_details(RecipeDetails(tags=('Pale Ale', ' pale ale ')))
        self.assertIn(('duplicate_tag', 'tags[1]'), {(issue.code, issue.path) for issue in validate_details(details)})

    def test_source_and_tag_bounds_are_explicit(self):
        invalid = RecipeDetails(source=' ' * 3, tags=('x' * 101,))
        self.assertIn(('invalid_source', 'source'), {(issue.code, issue.path) for issue in validate_details(invalid)})
        self.assertIn(('invalid_tag', 'tags[0]'), {(issue.code, issue.path) for issue in validate_details(invalid)})
        self.assertIn('too_many_tags', {issue.code for issue in validate_details(RecipeDetails(tags=('tag',) * 33))})

    def test_volume_target_purposes_are_unique_and_optional(self):
        details = RecipeDetails(volume_targets=(
            VolumeTarget('kettle', Decimal('25'), 'L'),
            VolumeTarget('fermenter', Decimal('19'), 'L'),
        ))
        self.assertEqual(validate_details(details), ())
        duplicate = RecipeDetails(volume_targets=(
            VolumeTarget('kettle', Decimal('25'), 'L'),
            VolumeTarget('kettle', Decimal('20'), 'US_gal'),
        ))
        self.assertIn('duplicate_target_purpose', {issue.code for issue in validate_details(duplicate)})

    def test_volume_target_rejects_unknown_tokens_and_inexact_or_invalid_amounts(self):
        for amount, unit in ((Decimal('0'), 'L'), (Decimal('-1'), 'L'),
                             (Decimal('NaN'), 'L'), (Decimal('1.0000000000001'), 'L'),
                             (Decimal('1000000000000'), 'L'), (Decimal('1'), 'g')):
            with self.subTest(amount=amount, unit=unit):
                details = RecipeDetails(volume_targets=(VolumeTarget('fermenter', amount, unit),))
                self.assertTrue(validate_details(details))


if __name__ == '__main__':
    unittest.main()
