"""Draft storage contract; no HTTP, database, or publication dependencies."""
from dataclasses import dataclass
from typing import Protocol

from .recipe_plan import PlanIssue, RecipePlan, validate_plan


@dataclass(frozen=True)
class RecipeDraft:
    recipe_id: str
    version_number: int
    plan: RecipePlan
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class StoredDraft:
    draft: RecipeDraft
    edit_revision: int


class InvalidDraft(ValueError):
    def __init__(self, issues: tuple[PlanIssue, ...]):
        self.issues = issues
        super().__init__('Recipe draft validation failed.')


class DraftConflict(ValueError):
    """The draft identity exists or the caller's edit revision is stale."""


class DraftNotFound(LookupError):
    """The selected draft does not exist."""


def validate_draft(draft: RecipeDraft) -> tuple[PlanIssue, ...]:
    issues = list(validate_plan(draft.plan))
    if not draft.recipe_id or draft.recipe_id.strip() != draft.recipe_id:
        issues.append(PlanIssue('invalid_id', 'recipe_id', 'Supply a nonempty recipe identifier without surrounding whitespace.'))
    if type(draft.version_number) is not int or draft.version_number < 1:
        issues.append(PlanIssue('invalid_version', 'version_number', 'Version numbers must be positive integers.'))
    if draft.name is not None and not draft.name.strip():
        issues.append(PlanIssue('invalid_name', 'name', 'Supply a recipe name, or leave it absent.'))
    return tuple(issues)


class RecipeDraftStore(Protocol):
    def create(self, draft: RecipeDraft) -> StoredDraft: ...

    def load(self, version_id: str) -> StoredDraft | None: ...

    def save(self, draft: RecipeDraft, expected_revision: int) -> StoredDraft: ...
