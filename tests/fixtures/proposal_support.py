"""Synthetic proposal snapshots; never production data or manufacturer claims."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from brewery_domain.conversion_proposals import ConversionProposal, IngredientConversion
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
                              StoredDraft(draft, 1), proposed, (profile,), (conversion,))



def seed_proposal(engine):
    from brewery_database.catalogue import PostgresFermentableCatalog
    from brewery_database.recipes import PostgresRecipeDraftStore
    value = proposal()
    PostgresRecipeDraftStore(engine).create(value.original.draft)
    catalogue = PostgresFermentableCatalog(engine)
    for profile in value.catalogue:
        catalogue.append(profile)
    return value
