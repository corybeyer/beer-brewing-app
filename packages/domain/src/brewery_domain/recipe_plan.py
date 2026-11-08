"""Structural recipe-plan rules for M2/UI-02/UI-04 (AC-01 and AC-02).

This check accepts incomplete plans. An empty issue list is not permission to
publish or start a batch. Adapters must provide typed values and a complete
version-local collection, then persist atomically only after validation.
"""
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction


MASS_UNITS = frozenset({'g', 'kg', 'oz', 'lb'})
UNITS = MASS_UNITS | frozenset({'mL', 'L', 'US_fl_oz', 'US_gal', 'count', 'packet'})
INGREDIENT_CATEGORIES = frozenset({'grain', 'hops', 'yeast', 'other'})


@dataclass(frozen=True)
class Ingredient:
    id: str
    version_id: str
    quantity: Decimal | None = None
    unit: str | None = None
    name: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class Step:
    id: str
    version_id: str
    dependencies: tuple[str, ...] = ()
    anchor_step_id: str | None = None
    title: str | None = None
    instructions: str | None = None


@dataclass(frozen=True)
class Addition:
    version_id: str
    step_id: str
    ingredient_id: str
    quantity: Decimal | None = None
    unit: str | None = None


@dataclass(frozen=True)
class RecipePlan:
    version_id: str
    ingredients: tuple[Ingredient, ...] = ()
    steps: tuple[Step, ...] = ()
    additions: tuple[Addition, ...] = ()


@dataclass(frozen=True)
class PlanIssue:
    code: str
    path: str
    message: str


def validate_plan(plan: RecipePlan) -> tuple[PlanIssue, ...]:
    """Return deterministic, field-specific issues without changing the plan.

    Quantities use finite positive Decimal values. Portion totals compare exact
    values in the ingredient's own unit; conversion is deliberately unsupported.
    Missing amounts/units remain absent and never become zero.
    """
    issues = []

    def issue(code, path, message):
        issues.append(PlanIssue(code, path, message))

    def identifier(value, path):
        if not isinstance(value, str) or not value or value.strip() != value:
            issue('invalid_id', path, 'Supply a nonempty identifier without surrounding whitespace.')
            return False
        return True

    def quantity(value, path):
        if value is None:
            return False
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            issue('invalid_quantity', path, 'Supply a finite positive decimal quantity.')
            return False
        return True

    def unit(value, path):
        if value is not None and value not in UNITS:
            issue('invalid_unit', path, 'Choose a supported unit, or leave it absent.')

    identifier(plan.version_id, 'version_id')
    collections = {}
    for name, records in (('ingredients', plan.ingredients), ('steps', plan.steps)):
        indexed = {}
        for index, record in enumerate(records):
            path = f'{name}[{index}]'
            valid_id = identifier(record.id, path + '.id')
            if record.version_id != plan.version_id:
                issue('cross_version', path + '.version_id', 'This record belongs to another recipe version.')
            if valid_id:
                if record.id in indexed:
                    issue('duplicate_id', path + '.id', 'Identifiers must be unique within this collection.')
                else:
                    indexed[record.id] = record
        collections[name] = indexed
    ingredients, steps = collections['ingredients'], collections['steps']

    valid_amounts = []
    for index, ingredient in enumerate(plan.ingredients):
        path = f'ingredients[{index}]'
        valid_amounts.append(quantity(ingredient.quantity, path + '.quantity'))
        unit(ingredient.unit, path + '.unit')
        if ingredient.category is not None and ingredient.category not in INGREDIENT_CATEGORIES:
            issue('invalid_category', path + '.category', 'Choose grain, hops, yeast, or other, or leave it absent.')
        if ingredient.category in ('grain', 'hops') and ingredient.unit is not None and ingredient.unit not in MASS_UNITS:
            issue('invalid_unit_category', path + '.unit', 'Grain and hops quantities require a mass unit.')

    # Edges combine dependencies and timing anchors, independent of display order.
    edges = {key: set() for key in steps}
    for index, step in enumerate(plan.steps):
        references = [(key, f'steps[{index}].dependencies[{offset}]')
                      for offset, key in enumerate(step.dependencies)]
        if step.anchor_step_id is not None:
            references.append((step.anchor_step_id, f'steps[{index}].anchor_step_id'))
        for key, path in references:
            target = steps.get(key)
            if target is None:
                issue('unknown_step', path, 'Select a step in this recipe version.')
            elif target.version_id != plan.version_id:
                issue('cross_version', path, 'Referenced steps must belong to this recipe version.')
            elif key == step.id:
                issue('self_reference', path, 'A step cannot depend on or anchor to itself.')
            elif step.id in edges:
                edges[step.id].add(key)

    # Kahn's algorithm avoids recursion limits for long user-authored plans.
    pending = {key: len(required) for key, required in edges.items()}
    dependents = {key: [] for key in edges}
    for key, required in edges.items():
        for target in required:
            dependents[target].append(key)
    ready = deque(key for key, count in pending.items() if count == 0)
    visited = 0
    while ready:
        visited += 1
        for key in dependents[ready.popleft()]:
            pending[key] -= 1
            if pending[key] == 0:
                ready.append(key)
    if visited != len(edges):
        issue('cycle', 'steps', 'Dependencies and timing anchors must not form a cycle.')

    totals = {}
    for index, addition in enumerate(plan.additions):
        path = f'additions[{index}]'
        if addition.version_id != plan.version_id:
            issue('cross_version', path + '.version_id', 'This addition belongs to another recipe version.')
        for field, records in (('step_id', steps), ('ingredient_id', ingredients)):
            target = records.get(getattr(addition, field))
            if target is None:
                issue('unknown_reference', path + '.' + field, 'Select a record in this recipe version.')
            elif target.version_id != plan.version_id:
                issue('cross_version', path + '.' + field, 'Addition references must belong to this recipe version.')
        valid = quantity(addition.quantity, path + '.quantity')
        unit(addition.unit, path + '.unit')
        ingredient = ingredients.get(addition.ingredient_id)
        if ingredient is not None:
            if addition.unit is not None and ingredient.unit is not None and addition.unit != ingredient.unit:
                issue('unit_mismatch', path + '.unit', 'Use the ingredient unit; automatic conversion is not supported.')
            elif valid and addition.unit is not None and ingredient.unit is not None:
                totals[ingredient.id] = totals.get(ingredient.id, Fraction()) + Fraction(addition.quantity)
    for index, ingredient in enumerate(plan.ingredients):
        if valid_amounts[index] and totals.get(ingredient.id, Fraction()) > Fraction(ingredient.quantity):
            issue('overallocated', f'ingredients[{index}].quantity', 'Scheduled portions exceed the ingredient quantity.')
    return tuple(issues)
