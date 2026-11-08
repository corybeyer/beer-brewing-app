"""Only reviewed forward transitions may migrate; recovery retains recipe data."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from infrastructure.deployment.production.rollout import BASELINE, RECIPES, Deployment


class RecipeRolloutTests(unittest.TestCase):
    def deployment(self, root, previous=BASELINE):
        (root / '.env').write_text('retained environment')
        if previous:
            (root / 'state.json').write_text(json.dumps({'application': 'old-app', 'operator': 'old-operator'}))
        return Deployment(root, root / 'backups')

    def contracts(self, target=RECIPES, previous=BASELINE, operator=None):
        def command(*arguments, **options):
            image = arguments[arguments.index('python') + 1]
            return (previous if image == 'old-app' else (operator or target) if image == 'operator' else target).encode()
        return command

    def test_successful_baseline_upgrade_checks_result_and_records_schema(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            deployment = self.deployment(root)
            order = []
            with (
                patch.object(deployment, 'command', side_effect=self.contracts()),
                patch.object(deployment, 'revision', side_effect=[BASELINE, RECIPES]),
                patch.object(deployment, 'compose', side_effect=lambda *args: order.append(args)),
                patch.object(deployment, 'backup', side_effect=lambda: order.append(('backup',))),
                patch.object(deployment, 'validate_service'),
            ):
                deployment.deploy_images('app', 'operator')
            self.assertLess(order.index(('backup',)), order.index(('run', '--rm', '--no-deps', 'migrate')))
            self.assertEqual(json.loads((root / 'state.json').read_text())['schema'], RECIPES)

    def test_failed_candidate_after_upgrade_uses_legacy_not_incompatible_old_api(self):
        self.failure_case(BASELINE, BASELINE, RECIPES, legacy=True, failing='candidate')

    def test_failed_cutover_after_upgrade_uses_legacy_without_downgrade(self):
        self.failure_case(BASELINE, BASELINE, RECIPES, legacy=True, failing='brewery')

    def test_failed_recipe_cutover_restores_compatible_recipe_api(self):
        self.failure_case(RECIPES, RECIPES, RECIPES, legacy=False, failing='brewery')

    def test_unknown_result_after_migration_uses_legacy(self):
        self.failure_case(BASELINE, BASELINE, RuntimeError('database unavailable'), legacy=True, failing='candidate')

    def failure_case(self, previous, before, after, legacy, failing):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            deployment = self.deployment(root, previous)
            validations = []

            def validate(service):
                validations.append(service)
                if service == failing and validations.count(service) == 1:
                    raise RuntimeError('candidate or switch failed')

            # Unknown result is encountered both on post-migrate check and recovery.
            revisions = [before, after, after]
            with (
                patch.object(deployment, 'command', side_effect=self.contracts(previous=previous)),
                patch.object(deployment, 'revision', side_effect=revisions),
                patch.object(deployment, 'compose') as compose,
                patch.object(deployment, 'backup'),
                patch.object(deployment, 'validate_service', side_effect=validate),
                patch.object(deployment, 'legacy_rollback') as rollback,
            ):
                with self.assertRaises(RuntimeError):
                    deployment.deploy_images('app', 'operator')
            self.assertEqual(rollback.call_count, int(legacy))
            self.assertEqual((root / '.env').read_text(), 'retained environment')
            self.assertNotIn('downgrade', repr(compose.call_args_list))
            self.assertNotIn('--volumes', repr(compose.call_args_list))
            if legacy:
                self.assertLessEqual(validations.count('brewery'), int(failing == 'brewery'))

    def test_reverse_unknown_and_mismatched_transitions_stop_before_migration(self):
        for target, current, operator in ((BASELINE, RECIPES, BASELINE),
                                           (RECIPES, '0003_unknown', RECIPES),
                                           (RECIPES, BASELINE, BASELINE),
                                           ('0003_unknown', BASELINE, '0003_unknown')):
            with self.subTest(target=target, current=current, operator=operator):
                with TemporaryDirectory() as directory:
                    root = Path(directory)
                    deployment = self.deployment(root)
                    with (
                        patch.object(deployment, 'command', side_effect=self.contracts(target=target, operator=operator)),
                        patch.object(deployment, 'revision', return_value=current),
                        patch.object(deployment, 'compose') as compose,
                        patch.object(deployment, 'backup') as backup,
                    ):
                        with self.assertRaises(ValueError):
                            deployment.deploy_images('app', 'operator')
                    backup.assert_not_called()
                    self.assertFalse(any('migrate' in call.args for call in compose.call_args_list))
                    self.assertEqual((root / '.env').read_text(), 'retained environment')
