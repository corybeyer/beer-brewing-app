"""Catalogue provenance, incomplete profiles, and exact grain-bill rules."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal, localcontext
import unittest

from brewery_domain.fermentable_catalogue import GrainComponent, IngredientColor, validate_catalog_revision


D = Decimal


from tests.fixtures.catalogue_support import grain, extract


class FermentableCatalogTests(unittest.TestCase):
    def codes(self, value):
        return {issue.code for issue in validate_catalog_revision(value)}

    def test_incomplete_profile_preserves_unknown_potential_and_color(self):
        value = replace(grain(), potential_ppg=None, potential_status='unknown', potential_note=None, color=None)
        self.assertEqual(validate_catalog_revision(value), ())
        self.assertIsNone(value.potential_ppg)
        self.assertIsNone(value.color)
        self.assertEqual(value.components, ())

    def test_manufacturer_claim_requires_attributed_source(self):
        value = replace(grain(), potential_status='manufacturer', potential_note=None)
        self.assertIn('missing_source', self.codes(value))
        value = replace(value, manufacturer='Synthetic Maltster', source_url='https://example.test/sheet.pdf')
        self.assertEqual(validate_catalog_revision(value), ())

    def test_assumptions_require_notes_and_known_potential_requires_status(self):
        for value in (replace(grain(), potential_note=None), replace(extract(), composition_note=None)):
            self.assertIn('missing_assumption', self.codes(value))
        self.assertIn('missing_provenance', self.codes(replace(grain(), potential_status='unknown')))
        self.assertIn('missing_provenance', self.codes(replace(grain(), potential_ppg=None)))

    def test_complete_blend_shares_are_exact_under_low_decimal_precision(self):
        value = replace(extract(), components=(GrainComponent('g1', D('.1')), GrainComponent('g2', D('.2')), GrainComponent('g3', D('.7'))))
        with localcontext() as context:
            context.prec = 1
            self.assertEqual(validate_catalog_revision(value), ())
            self.assertIn('incomplete_composition', self.codes(replace(value, components=value.components[:-1])))

    def test_grain_cannot_contain_an_extract_bill_or_unknown_partial_composition(self):
        self.assertIn('grain_composition', self.codes(replace(extract(), kind='grain')))
        self.assertIn('composition_status', self.codes(replace(extract(), composition_status='unknown')))
        self.assertIn('composition_status', self.codes(replace(extract(), components=())))
        self.assertIn('duplicate_component', self.codes(replace(extract(), components=(GrainComponent('g1', D('.5')),) * 2)))

    def test_color_needs_a_range_and_explicit_measurement_basis(self):
        for color in (IngredientColor(D('3'), D('2'), 'lovibond', 'as supplied'),
                      IngredientColor(D('2'), D('3'), 'unknown', 'as supplied'),
                      IngredientColor(D('2'), D('3'), 'srm', ''),
                      IngredientColor(D('NaN'), D('3'), 'lovibond', 'as supplied')):
            with self.subTest(color=color):
                self.assertTrue(validate_catalog_revision(replace(grain(), color=color)))

    def test_invalid_numbers_do_not_become_trusted_product_yields(self):
        for number in (True, 37, 37.1, D('NaN'), D('sNaN'), D('Infinity'), D('-1'), D('0'), D('1e999999'), D('1.1234567890123')):
            with self.subTest(number=number):
                self.assertTrue(validate_catalog_revision(replace(grain(), potential_ppg=number)))

    def test_source_urls_and_timestamps_reject_missing_or_credentialed_values(self):
        self.assertIn('invalid_timestamp', self.codes(replace(grain(), source_retrieved_at=datetime(2026, 11, 8))))
        for url in ('file:///tmp/source', 'https://user:password@example.test/data', 'https://example.test:bad/data', 'https://'):
            with self.subTest(url=url):
                self.assertIn('invalid_source_url', self.codes(replace(grain(), source_url=url)))

    def test_descriptors_and_bounded_identifiers_are_explicit(self):
        self.assertIn('invalid_tag', self.codes(replace(grain(), flavor_tags=('malty', 'malty'))))
        self.assertIn('invalid_tag', self.codes(replace(grain(), flavor_tags=('Rich Roast!',))))
        self.assertIn('invalid_text', self.codes(replace(grain(), revision_id=' padded ')))
        self.assertIn('invalid_text', self.codes(replace(grain(), name='bad\x00name')))


    def test_source_urls_are_preserved_without_network_resolution(self):
        for url in ('https://example.test/sheet.pdf#page=2', 'http://localhost:8080/reference',
                    'https://[::1]:443/source', 'https://xn--e1afmkfd.xn--p1ai/source'):
            with self.subTest(url=url):
                self.assertEqual(validate_catalog_revision(replace(grain(), source_url=url)), ())
        for url in ('https://exa mple.test/sheet', 'https://example.test:65536/sheet',
                    'https://[invalid]/sheet', 'https://example..test/source'):
            with self.subTest(url=url):
                self.assertIn('invalid_source_url', self.codes(replace(grain(), source_url=url)))
