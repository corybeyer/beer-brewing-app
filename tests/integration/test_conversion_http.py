"""Calculator transport works without database connectivity or writes."""
import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from brewery_api.api import create_app


def conversion_request():
    return {'source_mass': {'amount': '3', 'unit': 'lb'},
            'source_yield': {'potential_ppg': '45', 'recovery_fraction': '1',
                             'comparison_point': 'kettle', 'provenance': 'Explicit illustrative DME assumption'},
            'target_yield': {'potential_ppg': '37', 'recovery_fraction': '0.75',
                             'comparison_point': 'kettle', 'provenance': 'Illustrative grain and mash recovery'},
            'target_unit': 'lb'}


class ConversionHTTPTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'DATABASE_URL': 'postgresql://localhost:1/unavailable'})
        environment.start()
        self.addCleanup(environment.stop)
        self.client = TestClient(create_app(), base_url='http://localhost')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def post(self, value=None, **options):
        return self.client.post('/api/v1/conversions/fermentable', json=conversion_request() if value is None else value, **options)

    def test_exact_conversion_retains_inputs_and_server_formatted_display_without_database(self):
        with patch.object(self.client.app.state.database, 'connect', side_effect=OperationalError('SQL', {}, Exception('private'))) as connect:
            response = self.post()
            connect.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.get('/api/v1/readiness').status_code, 503)
        result = response.json()
        self.assertEqual(result['amount'], {'numerator': '180', 'denominator': '37'})
        self.assertEqual(result['gravity_points_gallons'], {'numerator': '135', 'denominator': '1'})
        self.assertEqual(result['display_amount'], '4.864865')
        self.assertEqual(result['display_decimal_places'], 6)
        self.assertEqual(result['calculation_version'], 'gravity-equivalence/v1')
        for field in ('source_mass', 'source_yield', 'target_yield'):
            self.assertEqual(result[field], conversion_request()[field])
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_sourced_lme_to_dme_example_matches_exact_core(self):
        value = conversion_request()
        value['source_yield']['potential_ppg'] = '37'
        value['target_yield'].update(potential_ppg='45', recovery_fraction='1')
        result = self.post(value).json()
        self.assertEqual(result['amount'], {'numerator': '37', 'denominator': '15'})
        self.assertEqual(result['display_amount'], '2.466667')

    def test_float_boolean_unknown_fields_missing_fields_and_unbounded_decimal_text_fail(self):
        for amount in (3, 3.0, True, None, '', 'NaN', 'Infinity', '-1', '1e9999999', '1e2', ' 3', '0', '1' * 10000):
            with self.subTest(amount=type(amount)):
                value = conversion_request()
                value['source_mass']['amount'] = amount
                response = self.post(value)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['error']['code'], 'invalid_conversion')
                self.assertTrue(response.json()['error']['issues'])
        for field in ('source_mass', 'source_yield', 'target_yield', 'target_unit'):
            value = conversion_request()
            del value[field]
            self.assertEqual(self.post(value).status_code, 422)
        for target in ('root', 'nested'):
            value = conversion_request()
            (value if target == 'root' else value['target_yield'])['unexpected'] = 'not accepted'
            self.assertEqual(self.post(value).status_code, 422)

    def test_explicit_recovery_provenance_units_and_matching_comparison_point_are_required(self):
        for field, supplied in (('recovery_fraction', '0'), ('recovery_fraction', '1.1'),
                                ('potential_ppg', '0'), ('provenance', ''), ('provenance', '  '),
                                ('provenance', '\x00'), ('provenance', 'x' * 1001),
                                ('comparison_point', 'fermenter')):
            value = conversion_request()
            value['target_yield'][field] = supplied
            response = self.post(value)
            self.assertEqual(response.status_code, 422)
            self.assertIn('target_yield.' + field, [issue['path'] for issue in response.json()['error']['issues']])
        value = conversion_request()
        value['target_unit'] = 'L'
        self.assertEqual(self.post(value).status_code, 422)

    def test_tiny_and_large_valid_exact_results_do_not_break_display_formatting(self):
        for small in (True, False):
            value = conversion_request()
            value['source_mass']['amount'] = '0.000000000001' if small else '9999999999999'
            value['source_yield'].update(potential_ppg='0.000000000001' if small else '9999999999999', recovery_fraction='1')
            value['target_yield'].update(potential_ppg='9999999999999' if small else '0.000000000001',
                                         recovery_fraction='1' if small else '0.000000000001')
            response = self.post(value)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertRegex(result['display_amount'], r'^([0-9]+\.[0-9]{6}|<0\.000001)$')
            self.assertGreater(int(result['amount']['numerator']), 0)
            self.assertGreater(int(result['amount']['denominator']), 0)
            if small:
                self.assertEqual(result['display_amount'], '<0.000001')

    def test_maximum_fully_escaped_unicode_notes_fit_the_unchanged_request_budget(self):
        value = conversion_request()
        value['source_yield']['provenance'] = '🍺' * 1000
        value['target_yield']['provenance'] = '🍺' * 1000
        encoded = json.dumps(value, ensure_ascii=True)
        self.assertLess(len(encoded.encode('utf-8')), 32768)
        response = self.client.post('/api/v1/conversions/fermentable', content=encoded,
                                    headers={'content-type': 'application/json'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['target_yield']['provenance'], value['target_yield']['provenance'])

    def test_browser_boundary_rejects_foreign_origins_media_and_oversized_bodies(self):
        self.assertEqual(self.post(headers={'origin': 'http://foreign.example'}).status_code, 403)
        self.assertEqual(self.post(headers={'sec-fetch-site': 'cross-site'}).status_code, 403)
        self.assertEqual(self.post(headers={'host': 'foreign.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/v1/conversions/fermentable', content='plain', headers={'content-type': 'text/plain'}).status_code, 415)
        self.assertEqual(self.post(headers={'content-length': '32769'}).status_code, 413)
        self.assertEqual(self.client.post('/api/v1/conversions/fermentable', content=' ' * 32769, headers={'content-type': 'application/json'}).status_code, 413)
        response = self.client.post('/api/v1/conversions/fermentable', content='{', headers={'content-type': 'application/json'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'invalid_request')
        self.assertEqual(self.client.post('/api/v1/conversions/fermentable', content=b'\xff', headers={'content-type': 'application/json'}).status_code, 400)

    def test_new_validation_handler_keeps_existing_recipe_contract_and_liveness(self):
        response = self.client.post('/api/v1/recipe-drafts', json={})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error']['code'], 'validation_error')
        self.assertEqual(self.client.get('/health').status_code, 200)

    def test_openapi_exposes_conversion_success_validation_and_boundary_errors(self):
        operation = self.client.get('/api/v1/openapi.json').json()['paths']['/api/v1/conversions/fermentable']['post']
        self.assertTrue({'200', '400', '403', '413', '415', '422'} <= set(operation['responses']))
