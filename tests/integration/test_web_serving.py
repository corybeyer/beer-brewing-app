"""Built frontend serving stays separate from configuration and private files."""
from contextlib import contextmanager
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from brewery_api.api import create_app
from brewery_config import web_assets_directory


class WebServingTests(unittest.TestCase):
    @contextmanager
    def built_client(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / 'web'
            (build / 'assets').mkdir(parents=True)
            (build / 'index.html').write_text('<!doctype html><script src="/assets/app-123.js"></script>')
            (build / 'assets/app-123.js').write_text('console.log("built application");')
            (root / 'private').write_text('synthetic-private-value')
            (build / '.env').write_text('synthetic-private-value')
            (build / 'assets/escape.js').symlink_to(root / 'private')
            with patch.dict(os.environ, {
                'DATABASE_URL': 'postgresql://localhost/brewery',
                'WEB_ASSETS_DIRECTORY': str(build),
            }, clear=True):
                with TestClient(create_app()) as client:
                    yield client

    def test_built_html_and_assets_are_served_with_entry_revalidation(self):
        with self.built_client() as client:
            for path in ('/', '/index.html'):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('text/html', response.headers['content-type'])
                self.assertEqual(response.headers['cache-control'], 'no-cache')
                self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
                self.assertIn('/assets/app-123.js', response.text)
                self.assertEqual(client.head(path).status_code, 200)
                self.assertEqual(client.head(path).content, b'')
            asset = client.get('/assets/app-123.js')
            self.assertEqual(asset.status_code, 200)
            self.assertIn('javascript', asset.headers['content-type'])
            self.assertIn('built application', asset.text)

    def test_unknown_api_private_paths_and_symlink_escape_are_not_html(self):
        with self.built_client() as client:
            for path in ('/api/v1/missing', '/.env', '/.secrets/app-password',
                         '/run/secrets/app-password', '/component-examples.html', '/src/main.tsx',
                         '/assets/escape.js', '/assets/%2e%2e%2findex.html'):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn('synthetic-private-value', response.text)
            self.assertEqual(client.get('/health').json(), {'status': 'ok', 'service': 'beer-brewing-app'})
            schema = client.get('/api/v1/openapi.json').json()
            self.assertIn('/api/v1/readiness', schema['paths'])
            self.assertNotIn('/', schema['paths'])

    def test_configured_incomplete_build_fails_without_echoing_path(self):
        with TemporaryDirectory() as directory:
            for value in ('', 'relative/private-build', directory, directory + '/missing'):
                with self.subTest(value=value):
                    with patch.dict(os.environ, {'WEB_ASSETS_DIRECTORY': value}, clear=True):
                        with self.assertRaises(ValueError) as error:
                            create_app()
                        self.assertEqual(str(error.exception),
                                         'WEB_ASSETS_DIRECTORY must name a complete absolute frontend build directory')
            (Path(directory) / 'index.html').write_text('incomplete')
            with patch.dict(os.environ, {'WEB_ASSETS_DIRECTORY': directory}, clear=True):
                with self.assertRaises(ValueError):
                    web_assets_directory()

    def test_api_only_mode_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(web_assets_directory())
