"""Synthetic catalogue fixtures, never manufacturer data or production seeds."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from brewery_domain.fermentable_catalogue import CatalogRevision, GrainComponent, IngredientColor


D = Decimal


def grain(revision_id='grain-r1', product_id='grain', revision_number=1):
    return CatalogRevision(product_id, revision_id, revision_number, 'grain', 'Synthetic grain',
        'Synthetic test data', datetime(2026, 11, 8, tzinfo=timezone.utc),
        potential_ppg=D('37.123456789012'), potential_status='manual_assumption',
        potential_note='Illustrative potential, not a manufacturer specification.',
        color=IngredientColor(D('2'), D('3'), 'lovibond', 'Malt as supplied'),
        flavor_notes='Illustrative malt and toast character.', flavor_tags=('malty', 'toasty'))


def extract():
    return replace(grain('extract-r1', 'extract'), kind='dme', name='Synthetic extract',
        potential_ppg=D('45'), composition_status='manual_assumption', composition_note='Illustrative grain bill.',
        components=(GrainComponent('grain-r1', D('.9')), GrainComponent('grain-r2', D('.1'))))

