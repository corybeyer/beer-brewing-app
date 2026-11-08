"""Ingredient HTTP edits preserve the complete plan and its revision boundary."""
from dataclasses import replace
from decimal import Decimal
import json
from uuid import uuid4

from brewery_api.recipe_http import MAX_INGREDIENT_BODY_BYTES
from brewery_database.recipes import PostgresRecipeDraftStore
from brewery_domain.recipe_plan import Addition, Ingredient, Step
from tests.integration.test_recipe_http import PATH, RecipeHTTPTestCase


class RecipeIngredientTests(RecipeHTTPTestCase):
    # Reuse the disposable API fixture, not the overview scenarios.
    def ingredient_fixture(self):
        draft = self.create().json()
        store = PostgresRecipeDraftStore(self.engine)
        stored = store.load(draft['version_id'])
        plan = replace(stored.draft.plan,
            ingredients=(Ingredient('hops', draft['version_id'], Decimal('20.123456789012'), 'g', 'Cascade', 'hops'),),
            steps=(Step('boil', draft['version_id'], title='Boil'),),
            additions=(Addition(draft['version_id'], 'boil', 'hops', Decimal('10'), 'g'),))
        store.save(replace(stored.draft, plan=plan, name='Preserved overview'), 1)
        endpoint = f"{PATH}/{draft['version_id']}/ingredients"
        return store, endpoint, self.client.get(endpoint).json()

    def test_exact_ingredient_edits_preserve_metadata_steps_and_portions(self):
        store, endpoint, original = self.ingredient_fixture()
        self.assertEqual(original['ingredients'][0]['quantity'], '20.123456789012')
        body = {'expected_revision': 2, 'ingredients': [
            {**original['ingredients'][0], 'quantity': '11.000000000001'},
            {'id': str(uuid4()), 'name': None, 'category': 'yeast', 'quantity': None, 'unit': None}]}
        response = self.client.patch(endpoint, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['edit_revision'], 3)
        self.assertEqual(response.json()['ingredients'][0]['quantity'], '11.000000000001')
        current = store.load(original['version_id'])
        self.assertEqual(current.draft.name, 'Preserved overview')
        self.assertEqual(current.draft.plan.steps[0].title, 'Boil')
        self.assertEqual(current.draft.plan.additions[0].quantity, Decimal('10'))
        self.assertIsNone(current.draft.plan.ingredients[1].quantity)
        self.assertEqual(self.client.get(endpoint).json(), response.json())
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_broken_links_units_and_portion_totals_save_nothing(self):
        store, endpoint, original = self.ingredient_fixture()
        row = original['ingredients'][0]
        for ingredients, issue in [([], 'unknown_reference'), ([{**row, 'quantity': '9'}], 'overallocated'),
                ([{**row, 'unit': 'oz'}], 'unit_mismatch'), ([{**row, 'unit': 'L'}], 'invalid_unit_category'),
                ([row, row], 'duplicate_id')]:
            response = self.client.patch(endpoint, json={'expected_revision': 2, 'ingredients': ingredients})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn(issue, [item['code'] for item in response.json()['error']['issues']])
            self.assertEqual(self.client.get(endpoint).json(), original)
        self.assertEqual(len(store.load(original['version_id']).draft.plan.additions), 1)

    def test_strict_decimal_strings_body_limits_and_ownership(self):
        _, endpoint, original = self.ingredient_fixture()
        row = original['ingredients'][0]
        for fields in ({'quantity': 12.3}, {'quantity': 'NaN'}, {'quantity': '1e999999'},
                       {'quantity': '-1'}, {'quantity': '0'}, {'quantity': '1.1234567890123'},
                       {'quantity': '1000000000000'}, {'version_id': 'another-version'},
                       {'unit': 'cups'}, {'category': 'sugar'}, {'name': 'x' * 201}):
            response = self.client.patch(endpoint, json={'expected_revision': 2, 'ingredients': [{**row, **fields}]})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.client.get(endpoint).json(), original)
        self.assertEqual(self.client.patch(endpoint, json={'expected_revision': 2, 'ingredients': [row] * 101}).status_code, 422)
        self.assertEqual(self.client.patch(endpoint, json={'expected_revision': 2, 'ingredients': [], 'steps': []}).status_code, 422)
        self.assertEqual(self.client.patch(endpoint, headers={'Origin': 'https://evil.example'}, json={'expected_revision': 2, 'ingredients': []}).status_code, 403)
        self.assertEqual(self.client.get(f'{PATH}/missing/ingredients').status_code, 404)

    def test_overview_and_ingredient_writers_share_one_conflict_boundary(self):
        _, endpoint, original = self.ingredient_fixture()
        overview = f"{PATH}/{original['version_id']}/overview"
        self.assertEqual(self.client.patch(overview, json={'expected_revision': 2, 'name': 'Other device', 'description': None}).status_code, 200)
        response = self.client.patch(endpoint, json={'expected_revision': 2, 'ingredients': []})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(endpoint).json()['ingredients'], original['ingredients'])
        current = self.client.get(endpoint).json()
        response = self.client.patch(endpoint, json={'expected_revision': 3, 'ingredients': current['ingredients']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.patch(overview, json={'expected_revision': 3, 'name': 'Stale', 'description': None}).status_code, 409)
        self.assertEqual(self.client.get(f"{PATH}/{original['version_id']}").json()['name'], 'Other device')


    def test_maximum_unicode_rows_fit_and_oversized_streams_save_nothing(self):
        draft = self.create().json()
        endpoint = f"{PATH}/{draft['version_id']}/ingredients"
        rows = [{'id': f'{index:03}' + '🍺' * 125, 'name': '🌾' * 200,
                 'category': 'other', 'quantity': '999999999999.999999999999', 'unit': 'US_fl_oz'}
                for index in range(100)]
        encoded = json.dumps({'expected_revision': 1, 'ingredients': rows}, ensure_ascii=True).encode()
        self.assertGreater(len(encoded), 32768)
        self.assertLess(len(encoded), MAX_INGREDIENT_BODY_BYTES)
        headers = {'Content-Type': 'application/json'}
        response = self.client.patch(endpoint, content=encoded, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['ingredients'], rows)
        self.assertEqual(self.client.get(endpoint).json(), response.json())
        for content in (b'x' * (MAX_INGREDIENT_BODY_BYTES + 1),
                        iter([b'x' * MAX_INGREDIENT_BODY_BYTES, b'x'])):
            with self.subTest(streamed=not isinstance(content, bytes)):
                rejected = self.client.patch(endpoint, content=content, headers=headers)
                self.assertEqual(rejected.status_code, 413)
                self.assertEqual(rejected.json()['error']['code'], 'request_too_large')
                self.assertEqual(self.client.get(endpoint).json(), response.json())
        # The boundary itself is inclusive, including for chunked requests.
        encoded = json.dumps({'expected_revision': 2, 'ingredients': rows}).encode()
        at_limit = encoded + b' ' * (MAX_INGREDIENT_BODY_BYTES - len(encoded))
        accepted = self.client.patch(endpoint, content=iter([at_limit]), headers=headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()['edit_revision'], 3)
