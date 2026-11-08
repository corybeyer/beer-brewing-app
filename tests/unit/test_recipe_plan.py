"""M2 recipe graph/portion invariants, independent of HTTP and persistence."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, localcontext
import unittest

from brewery_domain.recipe_plan import Addition, Ingredient, RecipePlan, Step, validate_plan


class RecipePlanTests(unittest.TestCase):
    def plan(self):
        return RecipePlan('v1',
                          (Ingredient('hops', 'v1', Decimal('100'), 'g'),),
                          (Step('boil', 'v1'), Step('bitter', 'v1', anchor_step_id='boil'),
                           Step('aroma', 'v1', ('boil',), 'boil')),
                          (Addition('v1', 'bitter', 'hops', Decimal('60'), 'g'),
                           Addition('v1', 'aroma', 'hops', Decimal('40'), 'g')))

    def codes(self, plan):
        return {issue.code for issue in validate_plan(plan)}

    def test_parallel_additions_share_anchor_and_preserve_input(self):
        plan = self.plan()
        original = deepcopy(plan)
        self.assertEqual(validate_plan(plan), ())
        self.assertEqual(validate_plan(replace(plan, steps=tuple(reversed(plan.steps)))), ())
        self.assertEqual(plan, original)

    def test_incomplete_drafts_do_not_invent_amounts_or_readiness(self):
        self.assertEqual(validate_plan(RecipePlan('v1')), ())
        plan = RecipePlan('v1', (Ingredient('yeast', 'v1'),), (Step('pitch', 'v1'),),
                          (Addition('v1', 'pitch', 'yeast'),))
        self.assertEqual(validate_plan(plan), ())
        self.assertIsNone(plan.ingredients[0].quantity)

    def test_cross_version_hop_record_and_link_are_rejected(self):
        plan = self.plan()
        plan = replace(plan, ingredients=(replace(plan.ingredients[0], version_id='v2'),))
        issues = validate_plan(plan)
        self.assertTrue(any(i.code == 'cross_version' and i.path == 'ingredients[0].version_id' for i in issues))
        self.assertTrue(any(i.code == 'cross_version' and i.path == 'additions[0].ingredient_id' for i in issues))

    def test_absent_foreign_hop_link_is_not_resolved_by_name(self):
        plan = self.plan()
        plan = replace(plan, additions=(replace(plan.additions[0], ingredient_id='v2-hops'),))
        self.assertIn('unknown_reference', self.codes(plan))

    def test_foreign_step_addition_and_version_are_rejected(self):
        plan = self.plan()
        for changed in (replace(plan, steps=(Step('boil', 'v2'),)),
                        replace(plan, additions=(replace(plan.additions[0], version_id='v2'),)),
                        replace(plan, additions=(replace(plan.additions[0], step_id='foreign'),))):
            with self.subTest(plan=changed):
                self.assertTrue(self.codes(changed) & {'unknown_reference', 'cross_version'})

    def test_dependencies_and_anchors_are_checked_together(self):
        plan = RecipePlan('v1', steps=(Step('mash', 'v1', ('transfer',)),
                                       Step('transfer', 'v1', anchor_step_id='mash')))
        self.assertIn('cycle', self.codes(plan))
        self.assertEqual(validate_plan(plan), validate_plan(plan))

    def test_dependency_only_and_anchor_only_cycles(self):
        for steps in ((Step('a', 'v1', ('b',)), Step('b', 'v1', ('c',)), Step('c', 'v1', ('a',))),
                      (Step('a', 'v1', anchor_step_id='b'), Step('b', 'v1', anchor_step_id='a'))):
            with self.subTest(steps=steps):
                self.assertIn('cycle', self.codes(RecipePlan('v1', steps=steps)))

    def test_self_links_missing_and_cross_version_steps(self):
        for step, expected in ((Step('a', 'v1', ('a',)), 'self_reference'),
                               (Step('a', 'v1', anchor_step_id='a'), 'self_reference'),
                               (Step('a', 'v1', ('missing',)), 'unknown_step'),
                               (Step('a', 'v1', anchor_step_id='missing'), 'unknown_step')):
            with self.subTest(step=step):
                self.assertIn(expected, self.codes(RecipePlan('v1', steps=(step,))))
        plan = RecipePlan('v1', steps=(Step('a', 'v1', ('b',)), Step('b', 'v2')))
        self.assertIn('cross_version', self.codes(plan))

    def test_duplicate_ids_are_rejected_in_each_collection(self):
        plan = self.plan()
        for changed in (replace(plan, ingredients=plan.ingredients * 2),
                        replace(plan, steps=plan.steps * 2)):
            self.assertIn('duplicate_id', self.codes(changed))

    def test_invalid_identifiers_have_field_paths(self):
        plan = RecipePlan('', (Ingredient(' ', ''),), (Step('', ''),))
        self.assertEqual({i.path for i in validate_plan(plan) if i.code == 'invalid_id'},
                         {'version_id', 'ingredients[0].id', 'steps[0].id'})

    def test_duplicate_ids_and_invalid_amounts_return_issues_together(self):
        plan = self.plan()
        invalid = replace(plan.ingredients[0], quantity=Decimal('NaN'))
        for ingredients in ((invalid, plan.ingredients[0]), (plan.ingredients[0], invalid)):
            with self.subTest(ingredients=ingredients):
                self.assertTrue({'duplicate_id', 'invalid_quantity'} <= self.codes(replace(plan, ingredients=ingredients)))

    def test_portion_totals_include_every_step(self):
        plan = self.plan()
        plan = replace(plan, additions=plan.additions + (Addition('v1', 'aroma', 'hops', Decimal('.01'), 'g'),))
        self.assertIn('overallocated', self.codes(plan))
        self.assertEqual(validate_plan(plan)[-1].path, 'ingredients[0].quantity')

    def test_partial_allocations_are_allowed(self):
        plan = self.plan()
        self.assertEqual(validate_plan(replace(plan, additions=plan.additions[:1])), ())

    def test_decimal_comparison_does_not_round_with_callers_context(self):
        plan = self.plan()
        plan = replace(plan, ingredients=(replace(plan.ingredients[0], quantity=Decimal('.3')),),
                       additions=(replace(plan.additions[0], quantity=Decimal('.1')),
                                  replace(plan.additions[1], quantity=Decimal('.2'))))
        with localcontext() as context:
            context.prec = 1
            self.assertEqual(validate_plan(plan), ())
            plan = replace(plan, additions=plan.additions + (Addition('v1', 'aroma', 'hops', Decimal('.0001'), 'g'),))
            self.assertIn('overallocated', self.codes(plan))

    def test_quantities_reject_zero_negative_nonfinite_and_float_values(self):
        plan = self.plan()
        for value in (Decimal('0'), Decimal('-1'), Decimal('NaN'), Decimal('sNaN'),
                      Decimal('Infinity'), Decimal('-Infinity'), 0.1, True):
            with self.subTest(value=value):
                ingredient = replace(plan.ingredients[0], quantity=value)
                addition = replace(plan.additions[0], quantity=value)
                self.assertIn('invalid_quantity', self.codes(replace(plan, ingredients=(ingredient,))))
                self.assertIn('invalid_quantity', self.codes(replace(plan, additions=(addition,))))

    def test_unit_mismatch_requires_explicit_conversion_before_validation(self):
        plan = self.plan()
        self.assertIn('unit_mismatch', self.codes(replace(plan, additions=(replace(plan.additions[0], unit='oz'),))))
        for value in ('', ' g '):
            self.assertIn('invalid_unit', self.codes(replace(plan, ingredients=(replace(plan.ingredients[0], unit=value),))))
        self.assertEqual(validate_plan(replace(plan, ingredients=(replace(plan.ingredients[0], unit=None),))), ())

    def test_controlled_categories_and_units_are_checked_for_incomplete_drafts(self):
        plan = self.plan()
        for category, unit, expected in (('unknown', 'g', 'invalid_category'),
                                         ('hops', 'L', 'invalid_unit_category'),
                                         ('grain', 'packet', 'invalid_unit_category'),
                                         (None, 'unknown', 'invalid_unit')):
            ingredient = replace(plan.ingredients[0], category=category, unit=unit)
            with self.subTest(category=category, unit=unit):
                self.assertIn(expected, self.codes(replace(plan, ingredients=(ingredient,), additions=())))

    def test_long_plans_do_not_depend_on_python_recursion_limit(self):
        steps = tuple(Step(str(i), 'v1', (str(i - 1),) if i else ()) for i in range(3000))
        plan = RecipePlan('v1', steps=steps)
        self.assertEqual(validate_plan(plan), ())
        self.assertIn('cycle', self.codes(replace(plan, steps=(replace(steps[0], dependencies=('2999',)),) + steps[1:])))
