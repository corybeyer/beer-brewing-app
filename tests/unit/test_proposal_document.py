"""Exact closed document encoding, fail-closed parsing, and resource limits."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
import json
import unittest
from unittest.mock import patch

from brewery_database.proposal_document import decode_proposal, encode_proposal
from brewery_domain.conversion_proposals import InvalidConversionProposal
from tests.fixtures.proposal_support import proposal


class ProposalDocumentTests(unittest.TestCase):
    def test_exact_round_trip_through_real_json_without_floats_or_mutable_collections(self):
        value = proposal()
        document = encode_proposal(value)
        with localcontext() as context:
            context.prec = 1
            restored = decode_proposal(json.loads(json.dumps(document)))
        self.assertEqual(restored, value)
        self.assertIsInstance(restored.proposed.plan.ingredients, tuple)
        self.assertEqual(restored.conversions[0].result.amount, Fraction(180, 37))
        self.assertIsInstance(restored.proposed.plan.ingredients[0].quantity, Decimal)
        self.assertIn('fraction', document['fields']['conversions'][0]['fields']['result']['fields']['amount'])

    def test_unknown_tags_fields_versions_and_python_class_names_fail_closed(self):
        document = encode_proposal(proposal())
        unknown_type = deepcopy(document)
        unknown_type['type'] = 'os.system'
        unknown_field = deepcopy(document)
        unknown_field['fields']['arbitrary'] = 'extra'
        missing_field = deepcopy(document)
        del missing_field['fields']['original']
        unknown_format = deepcopy(document)
        unknown_format['fields']['format_version'] = 'future/v3'
        for invalid in (unknown_type, unknown_field, missing_field, unknown_format,
                        {'pickle': 'not executable'}, [], 1.5):
            with self.subTest(invalid=type(invalid)), self.assertRaises((ValueError, InvalidConversionProposal)):
                decode_proposal(invalid)

    def test_timestamps_retain_the_instant_in_utc_even_with_subminute_offsets(self):
        value = proposal()
        changed = replace(value, created_at=value.created_at.astimezone(timezone(timedelta(seconds=1, microseconds=1))))
        document = encode_proposal(changed)
        self.assertEqual(decode_proposal(document), changed)
        self.assertTrue(document['fields']['created_at']['datetime'].endswith('+00:00'))

    def test_decimal_and_rational_resource_bounds_are_checked_before_expansion(self):
        for payload in ({'decimal': 'NaN'}, {'decimal': '1e999999999'}, {'decimal': 37},
                        {'fraction': ['1', '0']}, {'fraction': ['1', '-1']},
                        {'fraction': ['1' * 5000, '1']}, {'fraction': [1, 2]},
                        {'fraction': ['1', '2', '3']}):
            with self.subTest(payload=next(iter(payload))), self.assertRaises(ValueError):
                decode_proposal(payload)

    def test_corrupt_typed_nested_values_are_not_returned(self):
        document = encode_proposal(proposal())
        document['fields']['catalogue'][0]['fields']['source_retrieved_at'] = 'wrong type'
        with self.assertRaises((ValueError, InvalidConversionProposal)):
            decode_proposal(document)
        document = encode_proposal(proposal())
        document['fields']['conversions'][0]['fields']['result']['fields']['amount'] = {'fraction': ['5', '1']}
        with self.assertRaises(InvalidConversionProposal):
            decode_proposal(document)

    def test_size_depth_nul_and_unicode_are_checked_symmetrically(self):
        value = proposal()
        document = encode_proposal(value)
        size = len(json.dumps(document, ensure_ascii=False, sort_keys=True).encode('utf-8'))
        with patch('brewery_database.proposal_document.MAX_DOCUMENT_BYTES', size):
            self.assertEqual(decode_proposal(encode_proposal(value)), value)
        with patch('brewery_database.proposal_document.MAX_DOCUMENT_BYTES', size - 1):
            with self.assertRaises(ValueError):
                encode_proposal(value)
            with self.assertRaises(ValueError):
                decode_proposal(document)
        nested = None
        for _ in range(66):
            nested = [nested]
        with self.assertRaises(ValueError):
            decode_proposal(nested)
        changed = replace(value, original=replace(value.original, draft=replace(value.original.draft, description='NUL\x00')),
                          proposed=replace(value.proposed, description='NUL\x00'))
        with self.assertRaises(ValueError):
            encode_proposal(changed)
        unicode_value = replace(value, original=replace(value.original, draft=replace(value.original.draft, description='Malt 🍺 麦芽')),
                                proposed=replace(value.proposed, description='Malt 🍺 麦芽'))
        self.assertEqual(decode_proposal(encode_proposal(unicode_value)), unicode_value)
