"""Negative/positive fixtures for organization, dependency, and safety rules."""
import copy
import json
from pathlib import Path
import unittest

from scripts.validation.repository import filter_exceptions, lock_findings, migration_findings, python_checks, validate_policy

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / 'scripts/validation/policy.json').read_text())


class RepositoryValidatorTests(unittest.TestCase):
    def test_optional_native_dependencies_are_locked_for_other_platforms(self):
        packages = {
            'apps/web/node_modules/compiler': {'version': '7.0.2', 'optionalDependencies': {
                '@compiler/linux-arm64': '7.0.2', '@compiler/linux-x64': '7.0.2',
            }},
            'apps/web/node_modules/@compiler/linux-arm64': {'version': '7.0.2'},
        }
        files = {'package-lock.json': json.dumps({'packages': packages})}
        self.assertEqual({item['rule'] for item in lock_findings(files)}, {'manifest.optional-lock'})
        # A hoisted package is valid; resolution must follow Node's ancestors.
        packages['node_modules/@compiler/linux-x64'] = {'version': '7.0.2'}
        self.assertEqual(lock_findings({'package-lock.json': json.dumps({'packages': packages})}), [])
        packages['node_modules/@compiler/linux-x64']['version'] = '7.0.1'
        self.assertTrue(lock_findings({'package-lock.json': json.dumps({'packages': packages})}))

    def rules(self, files):
        return {item['rule'] for item in python_checks(files, POLICY)}

    def test_declared_backend_boundaries_and_comments_are_accepted(self):
        self.assertEqual(self.rules({
            'apps/api/brewery_api/api.py': 'from brewery_database.connection import database_is_ready\n# import sqlalchemy\n',
            'packages/domain/src/brewery_domain/recipe.py': 'from dataclasses import dataclass\n',
            'packages/config/src/brewery_config/__init__.py': 'import os\npassword = os.getenv("DATABASE_URL")\n',
        }), set())

    def test_wrong_owner_and_misplaced_sources_are_rejected(self):
        for path, expected in (
            ('random.py', 'layout.owner'), ('packages/misc/stuff.py', 'layout.owner'),
            ('docs/requirements/model.py', 'layout.source'),
            ('apps/api/view.tsx', 'layout.source'), ('packages/ui/src/server.py', 'layout.source'),
            ('apps/api/test_recipe.py', 'layout.test'), ('tests/backend/test_recipe.py', 'layout.test'),
            ('packages/database/recipe.schema.json', 'layout.contract'),
            ('apps/api/migrations/001.sql', 'layout.migration'), ('apps/web/package-lock.json', 'layout.lock'),
        ):
            with self.subTest(path=path):
                self.assertIn(expected, self.rules({path: '{}' if path.endswith('.json') else ''}))

    def test_domain_driver_transport_and_runtime_deployment_imports_fail(self):
        for path, code in (
            ('packages/domain/src/brewery_domain/rules.py', 'import sqlalchemy as db'),
            ('packages/domain/src/brewery_domain/rules.py', 'import urllib.request'),
            ('apps/api/brewery_api/api.py', 'from infrastructure.deployment.database import manage'),
            ('packages/config/src/brewery_config/__init__.py', 'import brewery_database'),
            ('apps/api/brewery_api/api.py', 'import sqlite3'),
        ):
            with self.subTest(code=code):
                self.assertIn('python.dependency', self.rules({path: code}))

    def test_literal_dynamic_imports_cannot_bypass_boundaries(self):
        path = 'packages/domain/src/brewery_domain/rules.py'
        self.assertIn('python.dependency', self.rules({path: 'import importlib\nimportlib.import_module("sqlalchemy")'}))
        self.assertIn('python.dynamic', self.rules({path: 'import importlib\nimportlib.import_module(module_name)'}))

    def test_environment_and_ddl_stay_out_of_api_handlers(self):
        for source, rule in (
            ('import os\nx = os.environ["DATABASE_URL"]', 'python.configuration'),
            ('import os as environment\nx = environment.environ.get("DATABASE_URL")', 'python.configuration'),
            ('from os import getenv as read\nx = read("DATABASE_URL")', 'python.configuration'),
            ('statement = "CREATE TABLE recipes (id int)"', 'python.ddl'),
            ('invalid python !!!', 'python.syntax'),
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, self.rules({'apps/api/brewery_api/api.py': source}))
        self.assertIn('python.syntax', self.rules({'scripts/broken.py': 'invalid python !!!'}))

    def test_policy_cannot_silently_widen_or_cycle_runtime_dependencies(self):
        validate_policy(POLICY)
        for uses in (['*'], ['database'], ['unknown']):
            policy = copy.deepcopy(POLICY)
            policy['owners']['config']['uses'] = uses
            with self.assertRaises(ValueError):
                validate_policy(policy)

    def test_python_relative_import_cannot_escape_package(self):
        self.assertIn('python.dependency', self.rules({
            'packages/config/src/brewery_config/config.py': 'from ...brewery_api import api',
        }))

    def test_sensitive_and_generated_files_are_rejected_without_values(self):
        for path in ('.env', '.secrets/password', 'data.sqlite3', 'infrastructure/private.key'):
            self.assertIn('security.file', self.rules({path: 'sensitive-value'}))
        for path in ('node_modules/demo/index.js', 'apps/web/dist/bundle.js', '.validation/pre-pr.json'):
            self.assertIn('layout.generated', self.rules({path: ''}))
        marker = '-----BEGIN ' + 'PRIVATE KEY-----'
        results = python_checks({'packages/config/leaked.txt': marker}, POLICY)
        self.assertIn('security.content', {item['rule'] for item in results})
        self.assertNotIn(marker, json.dumps(results))

    def test_archive_is_reference_only_and_document_links_are_checked(self):
        self.assertNotIn('layout.source', self.rules({'docs/references/source.py': 'import fastapi'}))
        self.assertIn('docs.link', self.rules({'docs/development/tool.md': '[Missing](gone.md)'}))
        self.assertEqual(self.rules({'docs/a.md': '[B](b.md#section)', 'docs/b.md': '# Section'}), set())

    def test_exception_requires_exact_path_reason_and_accepted_adr(self):
        path = 'apps/api/brewery_api/exception.py'
        files = {path: 'import sqlalchemy', 'docs/architecture/decisions/test.md': 'Status: Accepted'}
        results = python_checks(files, POLICY)
        policy = copy.deepcopy(POLICY)
        exception = {'rule': 'python.dependency', 'path': path, 'reason': 'Temporary adapter compatibility described in the decision.', 'adr': 'docs/architecture/decisions/test.md'}
        policy['exceptions'] = [exception]
        self.assertEqual(filter_exceptions(results, policy, files), [])
        for field, value in (('path', 'apps/**'), ('reason', 'because'), ('adr', 'missing.md'), ('rule', 'unknown'), ('rule', 'security.file')):
            broken = copy.deepcopy(policy)
            broken['exceptions'][0][field] = value
            self.assertIn('policy.exception', {item['rule'] for item in filter_exceptions(results, broken, files)})

    def test_migration_graph_and_readiness_revision_must_agree(self):
        base = {'packages/database/migrations/versions/001.py': 'revision = "one"\ndown_revision = None'}
        self.assertEqual(migration_findings(base), [])
        broken = {**base, 'packages/database/migrations/versions/002.py': 'revision = "two"\ndown_revision = "absent"'}
        self.assertIn('migration.graph', {item['rule'] for item in migration_findings(broken)})
        broken = {**base, 'packages/database/src/brewery_database/connection.py': 'SCHEMA_REVISION = "old"'}
        self.assertIn('migration.readiness', {item['rule'] for item in migration_findings(broken)})
        cycle = {'packages/database/migrations/versions/001.py': 'revision = "one"\ndown_revision = "one"'}
        self.assertIn('migration.graph', {item['rule'] for item in migration_findings(cycle)})
