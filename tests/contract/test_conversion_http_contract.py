"""Published calculator schemas are generated from the actual strict models."""
import json
from pathlib import Path
import unittest

from brewery_api.conversion_http import (
    ConversionErrorV1, FermentableConversionRequestV1, FermentableConversionResponseV1,
)


ROOT = Path(__file__).resolve().parents[2]


class ConversionContractTests(unittest.TestCase):
    def test_published_conversion_schemas_match_transport_models(self):
        for name, model in (('request', FermentableConversionRequestV1),
                            ('response', FermentableConversionResponseV1), ('error', ConversionErrorV1)):
            with self.subTest(name=name):
                stored = json.loads((ROOT / f'packages/communications/contracts/conversions/v1/{name}.schema.json').read_text())
                self.assertEqual(stored, {'$schema': 'https://json-schema.org/draft/2020-12/schema', **model.model_json_schema()})
