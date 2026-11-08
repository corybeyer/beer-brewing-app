"""Storage-port draft metadata validation stays independent of persistence."""
from dataclasses import replace
import unittest

from brewery_domain.recipe_plan import RecipePlan
from brewery_domain.recipes import RecipeDraft, validate_draft


class RecipeDraftTests(unittest.TestCase):
    def test_incomplete_metadata_preserves_absence(self):
        draft = RecipeDraft('recipe', 1, RecipePlan('version'))
        self.assertEqual(validate_draft(draft), ())
        self.assertIsNone(draft.name)
        self.assertIsNone(draft.description)

    def test_identity_version_number_and_blank_name_are_invalid(self):
        draft = RecipeDraft('recipe', 1, RecipePlan('version'))
        for changed, path in ((replace(draft, recipe_id=''), 'recipe_id'),
                              (replace(draft, recipe_id=' recipe'), 'recipe_id'),
                              (replace(draft, name='   '), 'name'),
                              *((replace(draft, version_number=value), 'version_number')
                                for value in (0, -1, True, 1.5))):
            with self.subTest(draft=changed):
                self.assertIn(path, {issue.path for issue in validate_draft(changed)})
