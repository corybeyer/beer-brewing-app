"""Optional descriptive metadata and volume targets for an editable recipe draft."""
from dataclasses import dataclass
from decimal import Decimal

from .recipe_plan import PlanIssue


VOLUME_PURPOSES = frozenset({'fermenter', 'kettle', 'packaged'})
VOLUME_UNITS = frozenset({'mL', 'L', 'US_fl_oz', 'US_gal'})
MAX_TAGS = 32
MAX_TAG_LENGTH = 100
MAX_SOURCE_LENGTH = 2000


@dataclass(frozen=True)
class VolumeTarget:
    purpose: str
    amount: Decimal
    unit: str


@dataclass(frozen=True)
class RecipeDetails:
    source: str | None = None
    tags: tuple[str, ...] = ()
    volume_targets: tuple[VolumeTarget, ...] = ()


def normalize_details(details: RecipeDetails) -> RecipeDetails:
    """Trim tag edges while keeping their display case and order."""
    return RecipeDetails(details.source, tuple(tag.strip() if isinstance(tag, str) else tag
                                               for tag in details.tags), details.volume_targets)


def validate_details(details: RecipeDetails) -> tuple[PlanIssue, ...]:
    """Validate bounded, optional draft metadata without converting user values."""
    issues: list[PlanIssue] = []

    def issue(code, path, message):
        issues.append(PlanIssue(code, path, message))

    if details.source is not None:
        if (not isinstance(details.source, str) or not details.source.strip() or '\x00' in details.source
                or len(details.source) > MAX_SOURCE_LENGTH):
            issue('invalid_source', 'source', 'Enter a nonblank recipe source of at most 2000 characters, or leave it absent.')

    if len(details.tags) > MAX_TAGS:
        issue('too_many_tags', 'tags', f'Use no more than {MAX_TAGS} recipe tags.')
    seen = set()
    for index, tag in enumerate(details.tags):
        path = f'tags[{index}]'
        if not isinstance(tag, str) or not tag or tag != tag.strip() or len(tag) > MAX_TAG_LENGTH or '\x00' in tag:
            issue('invalid_tag', path, f'Enter a trimmed, nonblank tag of at most {MAX_TAG_LENGTH} characters.')
            continue
        key = tag.casefold()
        if key in seen:
            issue('duplicate_tag', path, 'Recipe tags must be unique, ignoring letter case.')
        seen.add(key)

    if len(details.volume_targets) > len(VOLUME_PURPOSES):
        issue('too_many_volume_targets', 'volume_targets', 'Use at most one target for each supported volume purpose.')
    purposes = set()
    for index, target in enumerate(details.volume_targets):
        path = f'volume_targets[{index}]'
        if target.purpose not in VOLUME_PURPOSES:
            issue('invalid_target_purpose', path + '.purpose', 'Choose fermenter, kettle, or packaged volume.')
        elif target.purpose in purposes:
            issue('duplicate_target_purpose', path + '.purpose', 'Each volume purpose can have one target.')
        purposes.add(target.purpose)
        amount = target.amount
        if (not isinstance(amount, Decimal) or not amount.is_finite() or amount <= 0
                or amount >= Decimal('1000000000000') or amount.as_tuple().exponent < -12):
            issue('invalid_target_amount', path + '.amount', 'Enter a finite positive volume with at most 12 decimal places.')
        if target.unit not in VOLUME_UNITS:
            issue('invalid_target_unit', path + '.unit', 'Choose mL, L, US fluid ounces, or US gallons.')
    return tuple(issues)
