"""C2b domain snapshot evidence; these tests do not claim durable retention."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest

from brewery_domain.conversion_proposals import (
    ConversionProposal, IngredientConversion, InvalidConversionProposal, StaleConversionProposal,
    capture_proposal, require_current_proposal, validate_proposal,
)
from brewery_domain.extract_conversion import FermentableYield, Mass, convert_fermentable
from brewery_domain.recipe_plan import Addition, Ingredient, RecipePlan, Step
from brewery_domain.recipes import RecipeDraft, StoredDraft
from tests.fixtures.catalogue_support import grain


D = Decimal


def proposal():
    source = Ingredient('extract', 'v1', D('3'), 'lb', 'Manual DME', 'other')
    hops = Ingredient('hops', 'v1', D('1'), 'oz', 'Synthetic hops', 'hops')
    step = Step('mash', 'v1', title='Review mash procedure', instructions='Synthetic test plan')
    draft = RecipeDraft('r1', 1, RecipePlan('v1', (source, hops), (step,),
                        (Addition('v1', 'mash', 'extract', D('1.5'), 'lb'),)),
                        'Test recipe', 'Retain this description')
    result = convert_fermentable(Mass(D('3'), 'lb'),
        FermentableYield(D('45'), D('1'), 'kettle', 'Explicit illustrative DME assumption'),
        FermentableYield(D('37'), D('.75'), 'kettle', 'Synthetic grain and illustrative mash recovery'), 'lb')
    target = Ingredient('grain', 'v1', D('4.865'), 'lb', 'Synthetic grain', 'grain')
    proposed = replace(draft, plan=replace(draft.plan, ingredients=(target, hops),
                       additions=(Addition('v1', 'mash', 'grain', D('2.4325'), 'lb'),)))
    profile = replace(grain(), potential_ppg=D('37'))
    conversion = IngredientConversion('extract', 'grain', profile.revision_id, result,
        source_potential_override='Manual DME potential; original has no product link.',
        weighing_note='Round total to .001 lb; preserve equal scheduled halves.')
    return ConversionProposal('proposal-1', datetime(2026, 11, 8, tzinfo=timezone.utc),
                              StoredDraft(draft, 4), proposed, (profile,), (conversion,))


class ConversionProposalTests(unittest.TestCase):
    def codes(self, value):
        return {item.code for item in validate_proposal(value)}

    def change_conversion(self, value, **fields):
        return replace(value, conversions=(replace(value.conversions[0], **fields),))

    def test_captures_complete_original_proposed_and_exact_evidence_without_writes(self):
        value = proposal()
        self.assertIs(capture_proposal(value), value)
        self.assertEqual(value.conversions[0].result.amount, Fraction(180, 37))
        self.assertEqual(value.original.draft.plan.ingredients[0].quantity, D('3'))
        self.assertEqual(value.proposed.plan.ingredients[0].quantity, D('4.865'))
        self.assertEqual(value.original.draft.plan.additions[0].ingredient_id, 'extract')
        self.assertEqual(value.proposed.plan.additions[0].ingredient_id, 'grain')
        self.assertEqual(value.original.draft.description, value.proposed.description)
        with self.assertRaises(FrozenInstanceError):
            value.original.draft.name = 'Changed'
        with self.assertRaises(FrozenInstanceError):
            value.conversions[0].result.amount = Fraction(5)

    def test_independent_recipe_or_catalogue_changes_do_not_reinterpret_snapshot(self):
        value = proposal()
        edited = replace(value.original, edit_revision=5, draft=replace(value.original.draft, name='New name'))
        newer_profile = replace(value.catalogue[0], revision_id='grain-r2', revision_number=2, potential_ppg=D('38'))
        self.assertNotEqual(newer_profile.potential_ppg, value.catalogue[0].potential_ppg)
        self.assertNotEqual(edited.draft.name, value.original.draft.name)
        self.assertEqual(validate_proposal(value), ())

    def test_revision_guard_rejects_changed_revision_identity_or_same_revision_content(self):
        value = proposal()
        require_current_proposal(value, value.original)
        for current in (None, replace(value.original, edit_revision=5),
                        replace(value.original, draft=replace(value.original.draft, recipe_id='another')),
                        replace(value.original, draft=replace(value.original.draft, description='changed'))):
            with self.subTest(current=current), self.assertRaises(StaleConversionProposal):
                require_current_proposal(value, current)

    def test_tampered_output_points_or_calculation_version_is_rejected(self):
        value = proposal()
        for result in (replace(value.conversions[0].result, amount=Fraction(5)),
                       replace(value.conversions[0].result, gravity_points_gallons=Fraction(1)),
                       replace(value.conversions[0].result, calculation_version='future/v2'),
                       replace(value.conversions[0].result, amount=D('4.865'))):
            with self.subTest(result=result):
                self.assertIn('invalid_calculation', self.codes(self.change_conversion(value, result=result)))

    def test_missing_or_mismatched_yield_inputs_are_not_trusted(self):
        value = proposal()
        for target in (replace(value.conversions[0].result.target_yield, recovery_fraction=D('0')),
                       replace(value.conversions[0].result.target_yield, comparison_point='fermenter')):
            invalid = self.change_conversion(value, result=replace(value.conversions[0].result, target_yield=target))
            self.assertIn('invalid_calculation', self.codes(invalid))

    def test_product_yield_changes_require_explicit_override_and_full_profile(self):
        value = proposal()
        changed = replace(value, catalogue=(replace(value.catalogue[0], potential_ppg=D('38')),))
        self.assertIn('missing_override', self.codes(changed))
        self.assertEqual(validate_proposal(self.change_conversion(changed, target_potential_override='Explicit 37 PPG benchmark')), ())
        self.assertIn('missing_override', self.codes(self.change_conversion(value, source_potential_override=None)))
        self.assertIn('missing_profile', self.codes(replace(value, catalogue=())))
        unknown = replace(value, catalogue=(replace(value.catalogue[0], potential_ppg=None, potential_status='unknown'),))
        self.assertIn('missing_override', self.codes(unknown))

    def test_complete_extract_composition_snapshots_include_referenced_grains(self):
        from brewery_domain.fermentable_catalogue import GrainComponent
        value = proposal()
        profile = replace(value.catalogue[0], revision_id='dme-r1', product_id='dme', kind='dme',
                          composition_status='manual_assumption', composition_note='Synthetic blend',
                          components=(GrainComponent('grain-r1', D('1')),))
        changed = replace(value, catalogue=(profile,), proposed=replace(value.proposed,
            plan=replace(value.proposed.plan, ingredients=(replace(value.proposed.plan.ingredients[0], category='other'),
                                                          value.proposed.plan.ingredients[1]))))
        changed = self.change_conversion(changed, target_catalogue_revision_id='dme-r1')
        self.assertIn('missing_component', self.codes(changed))
        self.assertEqual(validate_proposal(replace(changed, catalogue=(profile, value.catalogue[0]))), ())

    def test_rounding_and_changed_portion_shares_need_explanations(self):
        value = proposal()
        self.assertIn('missing_weighing_note', self.codes(self.change_conversion(value, weighing_note=None)))
        result = convert_fermentable(Mass(D('3'), 'lb'), value.conversions[0].result.source_yield,
                                    replace(value.conversions[0].result.target_yield, potential_ppg=D('45'), recovery_fraction=D('1')), 'lb')
        exact = replace(value, catalogue=(replace(value.catalogue[0], potential_ppg=D('45')),),
            proposed=replace(value.proposed, plan=replace(value.proposed.plan,
                ingredients=(replace(value.proposed.plan.ingredients[0], quantity=D('3')), value.proposed.plan.ingredients[1]),
                additions=(replace(value.proposed.plan.additions[0], quantity=D('1.5')),))))
        exact = self.change_conversion(exact, result=result, weighing_note=None)
        self.assertEqual(validate_proposal(exact), ())
        changed = replace(exact, proposed=replace(exact.proposed, plan=replace(exact.proposed.plan,
                          additions=(replace(exact.proposed.plan.additions[0], quantity=D('1')),))))
        self.assertIn('changed_portion', self.codes(changed))

    def test_original_mass_must_match_full_calculated_source(self):
        value = proposal()
        for mass in (Mass(D('2'), 'lb'), Mass(D('3'), 'kg')):
            result = convert_fermentable(mass, value.conversions[0].result.source_yield, value.conversions[0].result.target_yield, 'lb')
            self.assertIn('source_mismatch', self.codes(self.change_conversion(value, result=result)))

    def test_unrelated_ingredient_changes_order_metadata_and_steps_are_rejected(self):
        value = proposal()
        for candidate, code in (
            (replace(value.proposed, name='Unrelated edit'), 'changed_identity'),
            (replace(value.proposed, recipe_id='r2'), 'changed_identity'),
            (replace(value.proposed, plan=replace(value.proposed.plan, steps=())), 'unknown_reference'),
            (replace(value.proposed, plan=replace(value.proposed.plan, ingredients=value.proposed.plan.ingredients[::-1])), 'changed_order'),
            (replace(value.proposed, plan=replace(value.proposed.plan, ingredients=(value.proposed.plan.ingredients[0],
                replace(value.proposed.plan.ingredients[1], quantity=D('2'))))), 'unexplained_change'),
            (replace(value.proposed, plan=replace(value.proposed.plan, steps=(replace(value.proposed.plan.steps[0], instructions='Changed'),))), 'changed_steps'),
        ):
            with self.subTest(code=code):
                self.assertIn(code, self.codes(replace(value, proposed=candidate)))

    def test_missing_or_rerouted_additions_are_rejected(self):
        value = proposal()
        missing = replace(value, proposed=replace(value.proposed, plan=replace(value.proposed.plan, additions=())))
        self.assertIn('changed_additions', self.codes(missing))
        rerouted = replace(value, proposed=replace(value.proposed, plan=replace(value.proposed.plan,
            steps=(*value.proposed.plan.steps, Step('boil', 'v1')),
            additions=(replace(value.proposed.plan.additions[0], step_id='boil'),))))
        self.assertIn('changed_link', self.codes(rerouted))

    def test_absent_portion_stays_absent_and_missing_units_do_not_support_scaling(self):
        value = proposal()
        original = replace(value.original, draft=replace(value.original.draft, plan=replace(value.original.draft.plan,
            additions=(replace(value.original.draft.plan.additions[0], quantity=None),))))
        unknown = replace(value, original=original)
        self.assertIn('invented_portion', self.codes(unknown))
        unknown = replace(unknown, proposed=replace(value.proposed, plan=replace(value.proposed.plan,
            additions=(replace(value.proposed.plan.additions[0], quantity=None),))))
        self.assertEqual(validate_proposal(unknown), ())
        no_unit = replace(value, original=replace(value.original, draft=replace(value.original.draft,
            plan=replace(value.original.draft.plan, additions=(replace(value.original.draft.plan.additions[0], unit=None),)))))
        self.assertIn('missing_portion', self.codes(no_unit))

    def test_mutable_nested_values_and_resource_bound_decimals_are_rejected(self):
        value = proposal()
        invalids = (replace(value, catalogue=list(value.catalogue)),
                    replace(value, conversions=list(value.conversions)),
                    replace(value, proposed=replace(value.proposed, plan=replace(value.proposed.plan, ingredients=list(value.proposed.plan.ingredients)))),
                    replace(value, proposed=replace(value.proposed, plan=replace(value.proposed.plan,
                        steps=(replace(value.proposed.plan.steps[0], dependencies=[]),)))),
                    replace(value, proposed=replace(value.proposed, plan=replace(value.proposed.plan,
                        ingredients=(replace(value.proposed.plan.ingredients[0], quantity=D('1e999999')),)))))
        for invalid in invalids:
            with self.subTest(invalid=type(invalid)), self.assertRaises(InvalidConversionProposal):
                capture_proposal(invalid)

    def test_duplicate_references_profiles_and_wrong_categories_are_rejected(self):
        value = proposal()
        self.assertIn('duplicate_conversion', self.codes(replace(value, conversions=value.conversions * 2)))
        self.assertIn('duplicate_profile', self.codes(replace(value, catalogue=value.catalogue * 2)))
        self.assertIn('unknown_ingredient', self.codes(self.change_conversion(value, target_ingredient_id='missing')))
        wrong = replace(value, proposed=replace(value.proposed, plan=replace(value.proposed.plan,
                        ingredients=(replace(value.proposed.plan.ingredients[0], category='other'), value.proposed.plan.ingredients[1]))))
        self.assertIn('profile_category', self.codes(wrong))

    def test_unknown_snapshot_or_calculation_format_and_missing_time_are_rejected(self):
        value = proposal()
        self.assertIn('unsupported_format', self.codes(replace(value, format_version='unknown')))
        self.assertIn('invalid_timestamp', self.codes(replace(value, created_at=datetime(2026, 11, 8))))
        self.assertIn('invalid_original', self.codes(replace(value, original=replace(value.original, edit_revision=True))))

    def test_capture_does_not_depend_on_decimal_context(self):
        value = proposal()
        with localcontext() as context:
            context.prec = 1
            self.assertEqual(validate_proposal(value), ())
            self.assertEqual(capture_proposal(value).conversions[0].result.amount, Fraction(180, 37))

    def test_unknown_portion_units_cannot_be_filled_by_assumption(self):
        value = proposal()
        original = replace(value.original, draft=replace(value.original.draft, plan=replace(value.original.draft.plan,
            additions=(replace(value.original.draft.plan.additions[0], quantity=None, unit=None),))))
        changed = replace(value, original=original, proposed=replace(value.proposed, plan=replace(value.proposed.plan,
            additions=(replace(value.proposed.plan.additions[0], quantity=None),))))
        self.assertIn('invented_portion', self.codes(changed))
        changed = replace(changed, proposed=replace(changed.proposed, plan=replace(changed.proposed.plan,
            additions=(replace(changed.proposed.plan.additions[0], unit=None),))))
        self.assertEqual(validate_proposal(changed), ())

    def test_product_identity_and_revision_numbers_agree_across_snapshots(self):
        value = proposal()
        changed_kind = replace(value.catalogue[0], revision_id='grain-r2', revision_number=2, kind='dme')
        duplicate_number = replace(value.catalogue[0], revision_id='same-number')
        self.assertIn('changed_product_kind', self.codes(replace(value, catalogue=(*value.catalogue, changed_kind))))
        self.assertIn('duplicate_revision', self.codes(replace(value, catalogue=(*value.catalogue, duplicate_number))))

    def test_invalid_typed_evidence_returns_issues_without_saving_or_crashing(self):
        value = proposal()
        for invalid in (None, replace(value, conversions=()), replace(value, conversions=(None,)),
                        self.change_conversion(value, result=None), self.change_conversion(value, weighing_note=' '),
                        replace(value, catalogue=(None,)), replace(value, proposed=None),
                        replace(value, original=None), replace(value, id=' padded ')):
            with self.subTest(invalid=type(invalid)), self.assertRaises(InvalidConversionProposal):
                capture_proposal(invalid)

    def test_weighing_explanation_cannot_bypass_plan_integrity(self):
        value = proposal()
        for addition, code in (
            (replace(value.proposed.plan.additions[0], quantity=D('100')), 'overallocated'),
            (replace(value.proposed.plan.additions[0], unit='kg'), 'unit_mismatch'),
            (replace(value.proposed.plan.additions[0], ingredient_id='missing'), 'unknown_reference'),
            (replace(value.proposed.plan.additions[0], version_id='v2'), 'cross_version'),
        ):
            with self.subTest(code=code):
                invalid = replace(value, proposed=replace(value.proposed,
                    plan=replace(value.proposed.plan, additions=(addition,))))
                self.assertIn(code, self.codes(invalid))

    def test_multiple_substitutions_preserve_unrelated_ingredients_and_steps(self):
        value = proposal()
        source = replace(value.original.draft.plan.ingredients[0], id='extract-2')
        target = replace(value.proposed.plan.ingredients[0], id='grain-2')
        changed = replace(value,
            original=replace(value.original, draft=replace(value.original.draft,
                plan=replace(value.original.draft.plan, ingredients=(*value.original.draft.plan.ingredients, source)))),
            proposed=replace(value.proposed, plan=replace(value.proposed.plan,
                ingredients=(*value.proposed.plan.ingredients, target))),
            conversions=(*value.conversions, replace(value.conversions[0], source_ingredient_id='extract-2', target_ingredient_id='grain-2')))
        self.assertEqual(validate_proposal(changed), ())
