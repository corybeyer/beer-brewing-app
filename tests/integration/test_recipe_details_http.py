"""The v1 details endpoint shares recipe edit revisions and stores volume purposes."""
from decimal import Decimal

from brewery_database.recipes import PostgresRecipeDraftStore
from tests.integration.test_recipe_http import PATH, RecipeHTTPTestCase


class RecipeDetailsHTTPTests(RecipeHTTPTestCase):
    def test_optional_details_round_trip_and_shared_revision(self):
        draft = self.create().json()
        endpoint = f"{PATH}/{draft['version_id']}/details"
        empty = self.client.get(endpoint)
        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json(), {
            'version_id': draft['version_id'], 'edit_revision': 1, 'source': None, 'tags': [], 'volume_targets': [],
        })
        saved = self.client.patch(endpoint, json={
            'expected_revision': 1, 'source': '  Brew notes  ', 'tags': [' Pale Ale ', 'Citrus'],
            'volume_targets': [
                {'purpose': 'kettle', 'amount': '25.5', 'unit': 'L'},
                {'purpose': 'fermenter', 'amount': '19', 'unit': 'L'},
            ],
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['edit_revision'], 2)
        self.assertEqual(saved.json()['source'], '  Brew notes  ')
        self.assertEqual(saved.json()['tags'], ['Pale Ale', 'Citrus'])
        self.assertEqual([item['purpose'] for item in saved.json()['volume_targets']], ['kettle', 'fermenter'])
        self.assertEqual(saved.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get(endpoint).json(), saved.json())

        changed = self.client.patch(f"{PATH}/{draft['version_id']}/overview", json={
            'expected_revision': 2, 'name': 'Tagged recipe', 'description': None,
        })
        self.assertEqual(changed.status_code, 200)
        stale = self.client.patch(endpoint, json={
            'expected_revision': 2, 'source': 'Stale source', 'tags': [], 'volume_targets': [],
        })
        self.assertEqual(stale.status_code, 409)
        current = self.client.get(endpoint).json()
        self.assertEqual(current['edit_revision'], 3)
        self.assertEqual(current['source'], '  Brew notes  ')
        self.assertEqual(current['tags'], ['Pale Ale', 'Citrus'])
        stored = PostgresRecipeDraftStore(self.engine).load(draft['version_id'])
        self.assertEqual(stored.draft.name, 'Tagged recipe')

    def test_invalid_details_are_rejected_without_partial_writes(self):
        draft = self.create().json()
        endpoint = f"{PATH}/{draft['version_id']}/details"
        good = {
            'expected_revision': 1, 'source': None, 'tags': ['Pale Ale'],
            'volume_targets': [{'purpose': 'kettle', 'amount': '25', 'unit': 'L'}],
        }
        invalid = [
            {'tags': ['Pale Ale', ' pale ale ']},
            {'tags': ['']},
            {'source': ' '},
            {'volume_targets': [{'purpose': 'kettle', 'amount': '0', 'unit': 'L'}]},
            {'volume_targets': [{'purpose': 'kettle', 'amount': '1.0000000000001', 'unit': 'L'}]},
            {'volume_targets': [{'purpose': 'mash', 'amount': '25', 'unit': 'L'}]},
            {'volume_targets': [{'purpose': 'kettle', 'amount': '25', 'unit': 'g'}]},
            {'unreviewed': True},
        ]
        for changed in invalid:
            with self.subTest(changed=changed):
                response = self.client.patch(endpoint, json={**good, **changed})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()['error']['code'], 'validation_error')
                current = self.client.get(endpoint).json()
                self.assertEqual(current['edit_revision'], 1)
                self.assertIsNone(current['source'])
                self.assertEqual(current['tags'], [])
                self.assertEqual(current['volume_targets'], [])

    def test_target_amounts_keep_exact_decimal_text_and_absence(self):
        draft = self.create().json()
        endpoint = f"{PATH}/{draft['version_id']}/details"
        response = self.client.patch(endpoint, json={
            'expected_revision': 1, 'source': None, 'tags': [],
            'volume_targets': [{'purpose': 'packaged', 'amount': '18.125000000001', 'unit': 'US_gal'}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['volume_targets'][0]['amount'], '18.125000000001')
        self.assertEqual(response.json()['volume_targets'][0]['unit'], 'US_gal')
        self.assertEqual(response.json()['source'], None)
