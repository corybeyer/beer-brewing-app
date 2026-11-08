"""Published v1 schemas must match the implemented transport models."""
import json
from pathlib import Path
import unittest

from brewery_api.recipe_http import CreateDraftV1, UpdateOverviewV1, RecipeOverviewV1, DraftPageV1, RecipeErrorV1, IngredientsV1, UpdateIngredientsV1


ROOT = Path(__file__).resolve().parents[2]


class RecipeContractTests(unittest.TestCase):
    def test_versioned_schemas_match_transport_models(self):
        for name, model in [('create-draft', CreateDraftV1), ('update-overview', UpdateOverviewV1),
                             ('ingredients', IngredientsV1), ('update-ingredients', UpdateIngredientsV1),
                             ('overview', RecipeOverviewV1), ('draft-page', DraftPageV1), ('error', RecipeErrorV1)]:
            with self.subTest(schema=name):
                path = ROOT / f'packages/communications/contracts/recipes/v1/{name}.schema.json'
                self.assertEqual(json.loads(path.read_text()), {
                    '$schema': 'https://json-schema.org/draft/2020-12/schema', **model.model_json_schema()})
