"""Immutable conversion proposals and their storage port; no adapters or ranking."""
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from typing import Protocol

from .extract_conversion import ConversionInputError, ConversionResult, FermentableYield, Mass, convert_fermentable
from .fermentable_catalogue import CatalogRevision, validate_catalog_revision
from .recipe_plan import Addition, Ingredient, PlanIssue, RecipePlan, Step
from .recipes import RecipeDraft, StoredDraft, validate_draft


@dataclass(frozen=True)
class IngredientConversion:
    source_ingredient_id: str
    target_ingredient_id: str
    target_catalogue_revision_id: str
    result: ConversionResult
    source_catalogue_revision_id: str | None = None
    source_potential_override: str | None = None
    target_potential_override: str | None = None
    weighing_note: str | None = None


@dataclass(frozen=True)
class ConversionProposal:
    id: str
    created_at: datetime
    original: StoredDraft
    proposed: RecipeDraft
    catalogue: tuple[CatalogRevision, ...]
    conversions: tuple[IngredientConversion, ...]
    format_version: str = 'conversion-proposal/v1'


class InvalidConversionProposal(ValueError):
    def __init__(self, issues: tuple[PlanIssue, ...]):
        self.issues = issues
        super().__init__('Conversion proposal validation failed.')


class StaleConversionProposal(ValueError):
    """Review refers to a different or edited draft; it must be regenerated."""


class ConversionProposalConflict(ValueError):
    """An immutable proposal identifier already exists."""


class ConversionProposalUnavailable(RuntimeError):
    """Proposal storage failed without exposing adapter details."""


class ConversionProposalStore(Protocol):
    def append(self, proposal: ConversionProposal) -> ConversionProposal: ...

    def load(self, proposal_id: str) -> ConversionProposal | None: ...

    def apply(self, proposal_id: str, expected_revision: int) -> StoredDraft: ...


def propose_single_grain_substitution(
    proposal_id: str,
    created_at: datetime,
    original: StoredDraft,
    source_ingredient_id: str,
    target: CatalogRevision,
    source_yield: FermentableYield,
    target_yield: FermentableYield,
    target_unit: str,
) -> ConversionProposal:
    """Create a reviewed one-grain proposal; never invent a bill or process input."""
    if (not isinstance(original, StoredDraft) or not isinstance(original.draft, RecipeDraft)
            or not isinstance(original.draft.plan, RecipePlan)):
        raise InvalidConversionProposal((PlanIssue('invalid_original', 'original',
            'Supply a complete saved recipe draft.'),))
    source = next((item for item in original.draft.plan.ingredients if item.id == source_ingredient_id), None)
    if source is None:
        raise InvalidConversionProposal((PlanIssue('unknown_ingredient', 'source_ingredient_id',
            'Choose an ingredient in the current recipe.'),))
    if source.category not in ('grain', 'other') or source.quantity is None or source.unit is None:
        raise InvalidConversionProposal((PlanIssue('unsupported_source', 'source_ingredient_id',
            'Choose a grain or other fermentable with a saved mass and unit.'),))
    if not isinstance(target, CatalogRevision) or target.kind != 'grain':
        raise InvalidConversionProposal((PlanIssue('invalid_target', 'target_catalogue_revision_id',
            'Choose a saved grain revision.'),))
    try:
        result = convert_fermentable(Mass(source.quantity, source.unit), source_yield,
                                     target_yield, target_unit)
    except (TypeError, ValueError) as error:
        if hasattr(error, 'path'):
            path = error.path
        else:
            path = 'calculation'
        raise InvalidConversionProposal((PlanIssue('invalid_calculation', path,
            'Provide valid explicit yields, recovery, units, and comparison point.'),)) from None
    with localcontext() as context:
        context.prec = 80
        try:
            weighing_amount = (Decimal(result.amount.numerator) / Decimal(result.amount.denominator)).quantize(Decimal('0.001'))
        except InvalidOperation:
            raise InvalidConversionProposal((PlanIssue('unsupported_amount', 'result.amount',
                'The converted amount exceeds the supported weighing range.'),)) from None
    if not weighing_amount.is_finite() or weighing_amount <= 0:
        raise InvalidConversionProposal((PlanIssue('invalid_weighing_amount', 'result.amount',
            'The converted amount is below the supported display precision.'),))
    weighing_note = (f'Display amount rounded to 0.001 {target_unit}; scheduled portions scaled to 12 decimal places; '
                     'verify your scale can measure the displayed amount.')
    target_ingredient_id = f'conversion-target-{proposal_id}'
    replacement = Ingredient(target_ingredient_id, source.version_id, weighing_amount, target_unit,
                              target.name, 'grain')
    ingredients = tuple(replacement if item.id == source.id else item for item in original.draft.plan.ingredients)
    additions = []
    for index, addition in enumerate(original.draft.plan.additions):
        if addition.ingredient_id != source.id:
            additions.append(addition)
            continue
        if addition.quantity is None:
            if addition.unit is not None and addition.unit != source.unit:
                raise InvalidConversionProposal((PlanIssue('portion_unit_mismatch',
                    f'original.plan.additions[{index}].unit', 'Review the existing scheduled portion unit before converting.'),))
            additions.append(Addition(addition.version_id, addition.step_id, target_ingredient_id,
                                      None, target_unit if addition.unit is not None else None))
            continue
        if addition.unit != source.unit:
            raise InvalidConversionProposal((PlanIssue('portion_unit_mismatch',
                f'original.plan.additions[{index}].unit', 'Review the existing scheduled portion unit before converting.'),))
        try:
            portion = Fraction(addition.quantity) * Fraction(weighing_amount) / Fraction(source.quantity)
            with localcontext() as context:
                context.prec = 80
                amount = (Decimal(portion.numerator) / Decimal(portion.denominator)).quantize(Decimal('0.000000000001'))
        except Exception:
            raise InvalidConversionProposal((PlanIssue('invalid_portion', f'original.plan.additions[{index}]',
                'The scheduled portion cannot be represented within the supported precision.'),)) from None
        additions.append(Addition(addition.version_id, addition.step_id, target_ingredient_id, amount, target_unit))
    proposed = replace(original.draft, plan=replace(original.draft.plan,
        ingredients=ingredients, additions=tuple(additions)))
    catalogue = (target,)
    conversion = IngredientConversion(source.id, target_ingredient_id, target.revision_id, result,
        source_potential_override=f'Explicit source assumption: {source_yield.provenance}',
        target_potential_override=(f'Explicit target assumption: {target_yield.provenance}'
            if target.potential_ppg != target_yield.potential_ppg else None),
        weighing_note=weighing_note.strip())
    value = ConversionProposal(proposal_id, created_at, original, proposed, catalogue, (conversion,))
    return capture_proposal(value)


def _text(value, optional=False):
    return (optional and value is None) or (isinstance(value, str) and bool(value.strip()) and '\x00' not in value)


def _draft_is_typed(draft):
    """Reject mutable collections before relying on a frozen outer dataclass."""
    if not isinstance(draft, RecipeDraft) or not isinstance(draft.plan, RecipePlan):
        return False
    if (not _text(draft.recipe_id) or not _text(draft.plan.version_id)
            or not _text(draft.name, optional=True)
            or draft.description is not None and not isinstance(draft.description, str)):
        return False
    for records, record_type in ((draft.plan.ingredients, Ingredient), (draft.plan.steps, Step),
                                 (draft.plan.additions, Addition)):
        if not isinstance(records, tuple) or any(not isinstance(item, record_type) for item in records):
            return False
    for ingredient in draft.plan.ingredients:
        if not _text(ingredient.id) or not _text(ingredient.name, optional=True):
            return False
    for step in draft.plan.steps:
        if (not _text(step.id) or not isinstance(step.dependencies, tuple)
                or any(not _text(key) for key in step.dependencies)
                or not _text(step.anchor_step_id, optional=True)
                or not _text(step.title, optional=True) or not _text(step.instructions, optional=True)):
            return False
    for addition in draft.plan.additions:
        if not _text(addition.step_id) or not _text(addition.ingredient_id):
            return False
    for item in (*draft.plan.ingredients, *draft.plan.additions):
        if item.unit is not None and not isinstance(item.unit, str):
            return False
        if isinstance(item, Ingredient) and item.category is not None and not isinstance(item.category, str):
            return False
        amount = item.quantity
        if amount is not None and (not isinstance(amount, Decimal) or not amount.is_finite()
                or len(amount.as_tuple().digits) > 24 or not -12 <= amount.as_tuple().exponent <= 12):
            return False
    return True


def validate_proposal(value: ConversionProposal) -> tuple[PlanIssue, ...]:
    issues = []

    def issue(code, path, message):
        issues.append(PlanIssue(code, path, message))

    if not isinstance(value, ConversionProposal):
        return (PlanIssue('invalid_proposal', '', 'Supply a typed conversion proposal.'),)
    if not _text(value.id) or value.id.strip() != value.id:
        issue('invalid_id', 'id', 'Supply an unpadded proposal identifier.')
    if value.format_version != 'conversion-proposal/v1':
        issue('unsupported_format', 'format_version', 'Use the supported proposal format.')
    if not isinstance(value.created_at, datetime) or value.created_at.utcoffset() is None:
        issue('invalid_timestamp', 'created_at', 'Supply an explicit timezone-aware proposal time.')
    if (not isinstance(value.original, StoredDraft) or type(value.original.edit_revision) is not int
            or value.original.edit_revision < 1):
        issue('invalid_original', 'original', 'Retain the stored draft and positive edit revision.')
        return tuple(issues)
    for label, draft in (('original.draft', value.original.draft), ('proposed', value.proposed)):
        if not _draft_is_typed(draft):
            issue('invalid_snapshot', label, 'Supply immutable typed recipe collections and bounded exact decimals.')
        else:
            issues.extend(replace(item, path=label + '.' + item.path) for item in validate_draft(draft))
    if issues:
        return tuple(issues)
    original, proposed = value.original.draft, value.proposed
    if replace(original, plan=proposed.plan) != proposed or original.plan.version_id != proposed.plan.version_id:
        issue('changed_identity', 'proposed', 'Retain recipe identity, version, name, and description.')
    if original.plan.steps != proposed.plan.steps:
        issue('changed_steps', 'proposed.plan.steps', 'Step adaptation requires a separately reviewed proposal format.')

    profiles = {}
    if not isinstance(value.catalogue, tuple) or len(value.catalogue) > 200:
        issue('invalid_catalogue', 'catalogue', 'Retain up to 200 immutable profile snapshots.')
        return tuple(issues)
    for index, profile in enumerate(value.catalogue):
        path = f'catalogue[{index}]'
        if not isinstance(profile, CatalogRevision):
            issue('invalid_profile', path, 'Retain the complete catalogue revision.')
            continue
        profile_issues = validate_catalog_revision(profile)
        issues.extend(PlanIssue(item.code, path + '.' + item.path, item.message) for item in profile_issues)
        if profile_issues:
            continue
        if profile.revision_id in profiles:
            issue('duplicate_profile', path, 'Retain each catalogue revision once.')
        profiles[profile.revision_id] = profile
    products, numbers = {}, set()
    for profile in profiles.values():
        if profile.product_id in products and products[profile.product_id] != profile.kind:
            issue('changed_product_kind', 'catalogue', 'A product cannot change kind between retained revisions.')
        products[profile.product_id] = profile.kind
        key = (profile.product_id, profile.revision_number)
        if key in numbers:
            issue('duplicate_revision', 'catalogue', 'Product revision numbers must identify one retained profile.')
        numbers.add(key)
        for component in profile.components:
            grain = profiles.get(component.grain_revision_id)
            if grain is None or grain.kind != 'grain':
                issue('missing_component', 'catalogue', 'Retain every referenced immutable grain revision.')

    if not isinstance(value.conversions, tuple) or not 1 <= len(value.conversions) <= 100:
        issue('invalid_conversions', 'conversions', 'Retain one to 100 immutable substitution calculations.')
        return tuple(issues)
    sources = {item.id: item for item in original.plan.ingredients}
    targets = {item.id: item for item in proposed.plan.ingredients}
    mappings = {}
    target_ids = set()
    for index, conversion in enumerate(value.conversions):
        path = f'conversions[{index}]'
        if not isinstance(conversion, IngredientConversion):
            issue('invalid_conversion', path, 'Supply typed ingredient conversion evidence.')
            continue
        fields = ('source_ingredient_id', 'target_ingredient_id', 'target_catalogue_revision_id')
        if (any(not _text(getattr(conversion, field)) for field in fields)
                or not _text(conversion.source_catalogue_revision_id, optional=True)
                or any(not _text(getattr(conversion, field), optional=True) for field in
                       ('source_potential_override', 'target_potential_override', 'weighing_note'))):
            issue('invalid_evidence', path, 'Use explicit identifiers and nonblank override/weighing explanations.')
            continue
        source, target = sources.get(conversion.source_ingredient_id), targets.get(conversion.target_ingredient_id)
        if source is None or target is None:
            issue('unknown_ingredient', path, 'Calculation references must resolve in the retained recipes.')
            continue
        if source.id in mappings or target.id in target_ids:
            issue('duplicate_conversion', path, 'Each ingredient participates in at most one one-to-one substitution.')
            continue
        mappings[source.id] = conversion
        target_ids.add(target.id)
        if source.category not in ('grain', 'other'):
            issue('source_category', path + '.source_ingredient_id', 'Explicitly classify the source as grain or other fermentable.')
        result = conversion.result
        if not isinstance(result, ConversionResult):
            issue('invalid_result', path + '.result', 'Retain the exact C1 calculation result.')
            continue
        try:
            expected = convert_fermentable(result.source_mass, result.source_yield, result.target_yield, result.unit)
        except ConversionInputError as error:
            issue('invalid_calculation', path + '.result.' + error.path, str(error))
            continue
        if (type(result.amount) is not Fraction or type(result.gravity_points_gallons) is not Fraction
                or result != expected):
            issue('invalid_calculation', path + '.result', 'Exact evidence must match the versioned C1 calculation.')
        if source.quantity is None or source.unit != result.source_mass.unit or Fraction(source.quantity) != result.source_mass.amount:
            issue('source_mismatch', path + '.result.source_mass', 'Convert the complete original ingredient mass in its recorded unit.')
        if target.quantity is None or target.unit != result.unit:
            issue('target_mismatch', path + '.result.unit', 'Supply the proposed weighing quantity in the result unit.')
        elif Fraction(target.quantity) != expected.amount and conversion.weighing_note is None:
            issue('missing_weighing_note', path + '.weighing_note', 'Explain rounding or adjustment; retain the unrounded result.')
        for side in ('source', 'target'):
            profile_id = getattr(conversion, side + '_catalogue_revision_id')
            profile = profiles.get(profile_id)
            override = getattr(conversion, side + '_potential_override')
            potential = getattr(result, side + '_yield').potential_ppg
            if profile is None and (side == 'target' or profile_id is not None):
                issue('missing_profile', path + '.' + side + '_catalogue_revision_id', 'Retain the selected complete catalogue revision.')
            if (profile is None or profile.potential_ppg != potential) and override is None:
                issue('missing_override', path + '.' + side + '_potential_override', 'Explain a manual, missing, or overridden product potential.')
            ingredient = source if side == 'source' else target
            if profile is not None and ingredient.category != ('grain' if profile.kind == 'grain' else 'other'):
                issue('profile_category', path + '.' + side + '_ingredient_id', 'The recipe category must agree with the selected profile kind.')

    expected_ids = tuple(mappings[item.id].target_ingredient_id if item.id in mappings else item.id
                         for item in original.plan.ingredients)
    if tuple(item.id for item in proposed.plan.ingredients) != expected_ids:
        issue('changed_order', 'proposed.plan.ingredients', 'Retain ingredient order and one target row per converted source.')
    for item in original.plan.ingredients:
        if item.id not in mappings and targets.get(item.id) != item:
            issue('unexplained_change', 'proposed.plan.ingredients', 'Preserve every ingredient outside the conversion evidence.')
    if len(original.plan.additions) != len(proposed.plan.additions):
        issue('changed_additions', 'proposed.plan.additions', 'Preserve every scheduled addition and its order.')
    for index, (before, after) in enumerate(zip(original.plan.additions, proposed.plan.additions)):
        conversion = mappings.get(before.ingredient_id)
        path = f'proposed.plan.additions[{index}]'
        if conversion is None:
            if before != after:
                issue('unexplained_change', path, 'Preserve unrelated scheduled additions.')
            continue
        target = targets[conversion.target_ingredient_id]
        if (before.version_id != after.version_id or before.step_id != after.step_id
                or after.ingredient_id != target.id):
            issue('changed_link', path, 'Retain the step and remap the addition to the converted ingredient.')
        if before.quantity is None:
            expected_unit = target.unit if before.unit is not None else None
            if after.quantity is not None or after.unit != expected_unit:
                issue('invented_portion', path, 'Keep unknown quantities/units absent; remap only an explicitly supplied unit.')
        elif (before.unit is None or sources[before.ingredient_id].quantity is None
              or after.quantity is None or after.unit != target.unit or target.quantity is None):
            issue('missing_portion', path, 'Known portions need explicit original and proposed mass units/amounts.')
        elif (Fraction(before.quantity) / Fraction(sources[before.ingredient_id].quantity)
              != Fraction(after.quantity) / Fraction(target.quantity)) and conversion.weighing_note is None:
            issue('changed_portion', path, 'Preserve exact portion shares or explain the weighing adjustment.')
    return tuple(issues)


def capture_proposal(value: ConversionProposal) -> ConversionProposal:
    """Validate an immutable value, without claiming it has been durably saved."""
    issues = validate_proposal(value)
    if issues:
        raise InvalidConversionProposal(issues)
    return value


def require_current_proposal(value: ConversionProposal, current: StoredDraft) -> None:
    """A review-time guard; a future save/apply transaction must check again."""
    capture_proposal(value)
    if current != value.original:
        raise StaleConversionProposal('The original draft changed; review a newly generated proposal.')
