"""Draft storage contract; no HTTP, database, or publication dependencies."""
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

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


@dataclass(frozen=True)
class RecipeOverview:
    recipe_id: str
    version_id: str
    version_number: int
    name: str | None
    description: str | None
    edit_revision: int


def overview(stored: StoredDraft) -> RecipeOverview:
    draft = stored.draft
    return RecipeOverview(draft.recipe_id, draft.plan.version_id, draft.version_number,
                          draft.name, draft.description, stored.edit_revision)


class InvalidDraft(ValueError):
    def __init__(self, issues: tuple[PlanIssue, ...]):
        self.issues = issues
        super().__init__('Recipe draft validation failed.')


class DraftConflict(ValueError):
    """The draft identity exists or the caller's edit revision is stale."""


class DraftNotFound(LookupError):
    """The selected draft does not exist."""


class RecipeStorageUnavailable(RuntimeError):
    """The adapter could not complete the operation; no driver details escape."""


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

    def list_drafts(self, limit: int, offset: int) -> tuple[RecipeOverview, ...]: ...


class RecipeDraftService:
    def __init__(self, store: RecipeDraftStore):
        self.store = store

    def create_empty(self, creation_id: UUID) -> tuple[RecipeOverview, bool]:
        version_id = str(uuid5(NAMESPACE_URL, f'brewery:recipe-draft:{creation_id}:1'))
        draft = RecipeDraft(str(creation_id), 1, RecipePlan(version_id))
        try:
            return overview(self.store.create(draft)), True
        except DraftConflict:
            existing = self.store.load(version_id)
            if existing is None or existing.draft.recipe_id != str(creation_id) or existing.draft.version_number != 1:
                raise
            return overview(existing), False

    def load(self, version_id: str) -> RecipeOverview:
        stored = self.store.load(version_id)
        if stored is None:
            raise DraftNotFound('The recipe draft does not exist.')
        return overview(stored)

    def update_overview(self, version_id: str, expected_revision: int,
                        name: str | None, description: str | None) -> RecipeOverview:
        current = self.store.load(version_id)
        if current is None:
            raise DraftNotFound('The recipe draft does not exist.')
        proposed = replace(current.draft, name=name, description=description)
        return overview(self.store.save(proposed, expected_revision))
