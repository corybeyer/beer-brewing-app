"""The v1 overview API uses real PostgreSQL and preserves the stored plan."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from unittest.mock import patch

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from brewery_api.api import create_app
from brewery_database.recipes import PostgresRecipeDraftStore
from brewery_domain.recipe_plan import Ingredient, Step
from tests.fixtures.postgres_support import PostgreSQLTestCase


PATH = '/api/v1/recipe-drafts'


class RecipeHTTPTests(PostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        command.upgrade(self.config, 'head')
        self.client = TestClient(create_app(), base_url='http://localhost')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def create(self, key=None):
        return self.client.post(PATH, json={'creation_id': key or str(uuid4())})

    def test_idempotent_create_returns_current_draft_after_retry(self):
        key = str(uuid4())
        first = self.create(key)
        self.assertEqual(first.status_code, 201)
        draft = first.json()
        self.assertIsNone(draft['name'])
        self.assertEqual(draft['status'], 'draft')
        self.assertEqual(self.create(key).json(), draft)
        self.assertEqual(self.create(key).status_code, 200)
        changed = self.client.patch(f"{PATH}/{draft['version_id']}/overview", json={
            'expected_revision': 1, 'name': 'Pale ale', 'description': 'My notes'})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.create(key).json(), changed.json())
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT count(*) FROM recipe_version')).scalar_one(), 1)

    def test_overview_update_preserves_ingredients_and_steps(self):
        data = self.create().json()
        store = PostgresRecipeDraftStore(self.engine)
        original = store.load(data['version_id'])
        plan = replace(original.draft.plan, ingredients=(Ingredient('yeast', data['version_id']),),
                       steps=(Step('pitch', data['version_id'], title='Pitch yeast'),))
        stored = store.save(replace(original.draft, plan=plan), 1)
        response = self.client.patch(f"{PATH}/{data['version_id']}/overview", json={
            'expected_revision': stored.edit_revision, 'name': 'Custom recipe', 'description': None})
        self.assertEqual(response.status_code, 200)
        current = store.load(data['version_id'])
        self.assertEqual(current.draft.plan, plan)
        self.assertEqual(current.draft.name, 'Custom recipe')
        self.assertEqual(current.edit_revision, 3)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_simultaneous_create_retries_produce_one_draft(self):
        key = str(uuid4())
        barrier = Barrier(2)

        def create():
            barrier.wait(timeout=5)
            return self.create(key)

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(create) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sorted(response.status_code for response in results), [200, 201])
        self.assertEqual(results[0].json(), results[1].json())

    def test_conflicts_keep_newer_data_and_invalid_payloads_save_nothing(self):
        draft = self.create().json()
        endpoint = f"{PATH}/{draft['version_id']}/overview"
        body = {'expected_revision': 1, 'name': 'First writer', 'description': None}
        self.assertEqual(self.client.patch(endpoint, json=body).status_code, 200)
        conflict = self.client.patch(endpoint, json={**body, 'name': 'Stale writer'})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()['error']['code'], 'conflict')
        for fields in ({'name': ' '}, {'expected_revision': True}, {'expected_revision': '2'},
                       {'name': 123}, {'name': 'x' * 201}, {'description': 'x' * 10001},
                       {'ingredients': []}, {'status': 'published'}):
            with self.subTest(fields=fields):
                response = self.client.patch(endpoint, json={**body, 'expected_revision': 2, **fields})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()['error']['code'], 'validation_error')
        self.assertEqual(self.client.get(f"{PATH}/{draft['version_id']}").json()['name'], 'First writer')
        self.assertEqual(self.client.get(f'{PATH}/missing').status_code, 404)

    def test_bounded_library_lists_metadata_with_pagination(self):
        for _ in range(3):
            self.create()
        first = self.client.get(PATH, params={'limit': 2}).json()
        self.assertEqual(len(first['items']), 2)
        self.assertEqual(first['next_offset'], 2)
        second = self.client.get(PATH, params={'limit': 2, 'offset': 2}).json()
        self.assertEqual(len(second['items']), 1)
        self.assertIsNone(second['next_offset'])
        self.assertNotEqual(first['items'][0]['version_id'], second['items'][0]['version_id'])
        self.assertNotIn('ingredients', first['items'][0])
        for parameters in ({'limit': 0}, {'limit': 101}, {'offset': -1}):
            self.assertEqual(self.client.get(PATH, params=parameters).status_code, 422)

    def test_foreign_browser_requests_and_hosts_are_rejected_before_writes(self):
        for headers in ({'Origin': 'https://evil.example'}, {'Origin': 'null'},
                        {'Origin': 'http://localhost.evil.example'}, {'Sec-Fetch-Site': 'cross-site'},
                        {'Host': 'evil.example'}, {'Host': 'localhost@evil.example'}):
            with self.subTest(headers=headers):
                response = self.client.post(PATH, headers=headers, json={'creation_id': str(uuid4())})
                self.assertEqual(response.status_code, 403)
        valid = self.client.post(PATH, headers={'Origin': 'http://localhost', 'Sec-Fetch-Site': 'same-origin'},
                                 json={'creation_id': str(uuid4())})
        self.assertEqual(valid.status_code, 201)
        proxy = self.client.post(PATH, headers={'Host': '127.0.0.1:5174', 'Origin': 'http://127.0.0.1:5174'},
                                 json={'creation_id': str(uuid4())})
        self.assertEqual(proxy.status_code, 201)
        self.assertEqual(self.client.post(PATH, headers={'Origin': 'http://localhost:8080'},
                                         json={'creation_id': str(uuid4())}).status_code, 403)
        for host in ('appHomebrew:8080', '192.168.1.10:8080', '100.117.8.59:8080', '[::1]:8080'):
            self.assertEqual(self.client.get(PATH, headers={'Host': host}).status_code, 200)

    def test_json_and_streamed_body_limits_are_enforced(self):
        self.assertEqual(self.client.post(PATH, content='{}', headers={'Content-Type': 'text/plain'}).status_code, 415)
        for content in ('x' * 32769, iter([b'x' * 16000, b'x' * 17000])):
            self.assertEqual(self.client.post(PATH, content=content, headers={'Content-Type': 'application/json'}).status_code, 413)
        invalid = self.client.post(PATH, content='{', headers={'Content-Type': 'application/json'})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.client.post(PATH, json={'creation_id': 'bad'}).status_code, 422)
        malformed = self.client.post(PATH, content=b'\xff', headers={'Content-Type': 'application/json'})
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(malformed.json()['error']['code'], 'invalid_request')

    def test_unavailable_database_is_sanitized_and_health_stays_live(self):
        unavailable = self.url.set(database='missing_' + uuid4().hex)
        with patch.dict('os.environ', {'DATABASE_URL': unavailable.render_as_string(hide_password=False)}):
            with TestClient(create_app(), base_url='http://localhost') as client:
                for response in (client.get(PATH), client.post(PATH, json={'creation_id': str(uuid4())})):
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()['error']['code'], 'unavailable')
                    self.assertNotIn(self.url.username, response.text)
                    self.assertNotIn(self.url.password, response.text)
                self.assertEqual(client.get('/health').status_code, 200)
