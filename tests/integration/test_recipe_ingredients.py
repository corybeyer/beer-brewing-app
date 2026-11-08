"""Ingredient HTTP edits preserve the complete plan and its revision boundary."""
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

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
