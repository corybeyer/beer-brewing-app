"""Versioned step editing validates links and preserves the rest of the plan."""
from dataclasses import replace
from decimal import Decimal
import json

from brewery_api.recipe_http import MAX_STEP_BODY_BYTES
from brewery_database.recipes import PostgresRecipeDraftStore
from brewery_domain.recipe_plan import Addition, Ingredient, Step
from tests.integration.test_recipe_http import PATH, RecipeHTTPTestCase


class RecipeStepTests(RecipeHTTPTestCase):
    def step_fixture(self):
        draft = self.create().json()
        store = PostgresRecipeDraftStore(self.engine)
        stored = store.load(draft['version_id'])
        version = draft['version_id']
        plan = replace(stored.draft.plan,
            ingredients=(Ingredient('grain', version, Decimal('4'), 'kg', 'Pale malt', 'grain'),),
            steps=(Step('mash', version, title='Mash'), Step('boil', version, ('mash',), 'mash', 'Boil')),
            additions=(Addition(version, 'mash', 'grain', Decimal('4'), 'kg'),))
        store.save(replace(stored.draft, plan=plan, name='Preserved recipe'), 1)
        endpoint = f'{PATH}/{version}/steps'
        response = self.client.get(endpoint)
        return store, endpoint, response.json()

    def test_ordered_step_edit_saves_and_preserves_step_links_and_other_plan_data(self):
        store, endpoint, original = self.step_fixture()
        self.assertEqual(original['linked_addition_step_ids'], ['mash'])
        self.assertEqual([item['id'] for item in original['steps']], ['mash', 'boil'])
        reordered = [dict(original['steps'][1], title='Rolling boil'), original['steps'][0]]
        response = self.client.patch(endpoint, json={'expected_revision': 2, 'steps': reordered})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['edit_revision'], 3)
        self.assertEqual([item['id'] for item in response.json()['steps']], ['boil', 'mash'])
        current = store.load(original['version_id'])
        self.assertEqual(current.draft.name, 'Preserved recipe')
        self.assertEqual(current.draft.plan.steps[0].dependencies, ('mash',))
        self.assertEqual(current.draft.plan.steps[0].anchor_step_id, 'mash')
        self.assertEqual(current.draft.plan.additions[0].step_id, 'mash')
        self.assertEqual(current.draft.plan.ingredients[0].name, 'Pale malt')
        self.assertEqual(self.client.get(endpoint).json(), response.json())
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_cycles_missing_references_and_removing_linked_steps_save_nothing(self):
        _, endpoint, original = self.step_fixture()
        steps = original['steps']
        invalid_plans = [
            ([dict(steps[0], dependencies=['boil']), dict(steps[1], dependencies=['mash'])], 'cycle'),
            ([dict(steps[0], anchor_step_id='missing'), steps[1]], 'unknown_reference'),
            ([steps[1]], 'unknown_reference'),
            ([dict(steps[0], id=' mash '), steps[1]], 'invalid_id'),
        ]
        for plan, issue in invalid_plans:
            with self.subTest(issue=issue):
                response = self.client.patch(endpoint, json={'expected_revision': 2, 'steps': plan})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn(issue, [item['code'] for item in response.json()['error']['issues']])
                self.assertEqual(self.client.get(endpoint).json(), original)

    def test_revision_is_shared_with_overview_and_stale_step_edit_conflicts(self):
        _, endpoint, original = self.step_fixture()
        overview = f"{PATH}/{original['version_id']}/overview"
        self.assertEqual(self.client.patch(overview, json={'expected_revision': 2, 'name': 'Changed elsewhere', 'description': None}).status_code, 200)
        response = self.client.patch(endpoint, json={'expected_revision': 2, 'steps': original['steps']})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(endpoint).json()['steps'], original['steps'])
        current = self.client.get(endpoint).json()
        response = self.client.patch(endpoint, json={'expected_revision': current['edit_revision'], 'steps': current['steps']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['edit_revision'], 4)

    def test_strict_shape_limits_origin_and_missing_draft(self):
        _, endpoint, original = self.step_fixture()
        row = original['steps'][0]
        for fields in ({'id': 3}, {'version_id': original['version_id']}, {'title': 'x' * 201},
                       {'instructions': 'x' * 2001}, {'dependencies': ['missing'] * 101}):
            response = self.client.patch(endpoint, json={'expected_revision': 2, 'steps': [{**row, **fields}, original['steps'][1]]})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.client.get(endpoint).json(), original)
        self.assertEqual(self.client.patch(endpoint, headers={'Origin': 'https://evil.example'},
            json={'expected_revision': 2, 'steps': original['steps']}).status_code, 403)
        self.assertEqual(self.client.get(f'{PATH}/missing/steps').status_code, 404)

    def test_step_body_limit_accepts_boundary_and_rejects_oversized_stream_without_saving(self):
        _, endpoint, original = self.step_fixture()
        body = json.dumps({'expected_revision': 2, 'steps': original['steps']}).encode()
        at_limit = body + b' ' * (MAX_STEP_BODY_BYTES - len(body))
        accepted = self.client.patch(endpoint, content=at_limit, headers={'Content-Type': 'application/json'})
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()['edit_revision'], 3)
        for content in (b'x' * (MAX_STEP_BODY_BYTES + 1), iter([b'x' * MAX_STEP_BODY_BYTES, b'x'])):
            response = self.client.patch(endpoint, content=content, headers={'Content-Type': 'application/json'})
            self.assertEqual(response.status_code, 413)
            self.assertEqual(response.json()['error']['code'], 'request_too_large')
            self.assertEqual(self.client.get(endpoint).json(), accepted.json())
