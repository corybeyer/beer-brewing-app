"""Explainable grain-bill matches and separately labeled variations; no sizing."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Literal

from .fermentable_catalogue import CatalogRevision, validate_catalog_revision


@dataclass(frozen=True)
class MatchReview:
    code: str
    revision_id: str | None = None


@dataclass(frozen=True)
class MatchedGrain:
    revision: CatalogRevision
    mass_fraction: Decimal


@dataclass(frozen=True)
class GrainMatch:
    id: str
    relation: Literal['manufacturer_composition', 'assumed_composition', 'variation', 'unranked_variation']
    components: tuple[MatchedGrain, ...]
    shared_flavor_tags: tuple[str, ...]
    tag_similarity: Fraction | None
    color_gap: Fraction | None
    review: tuple[MatchReview, ...]


@dataclass(frozen=True)
class GrainMatches:
    source: CatalogRevision
    options: tuple[GrainMatch, ...]
    review: tuple[MatchReview, ...]
    ranking_version: Literal['grain-ranking/v1'] = 'grain-ranking/v1'


class MatchingInputError(ValueError):
    def __init__(self, path: str, message: str):
        self.path = path
        super().__init__(message)


def _profile(value, path):
    if not isinstance(value, CatalogRevision):
        raise MatchingInputError(path, 'Supply a complete typed catalogue revision.')
    issues = validate_catalog_revision(value)
    if issues:
        raise MatchingInputError(path + '.' + issues[0].path, issues[0].message)


def _reviews(values):
    return tuple(sorted(set(values), key=lambda item: (item.code, item.revision_id or '')))


def _potential_review(profile, source=False):
    prefix = 'source_' if source else 'grain_'
    if profile.potential_ppg is None:
        return (MatchReview(prefix + 'potential_required', profile.revision_id),)
    if profile.potential_status == 'manual_assumption':
        return (MatchReview(prefix + 'potential_assumed', profile.revision_id),)
    return ()


def _variation(source, grain):
    review = list(_potential_review(grain))
    source_tags, grain_tags = set(source.flavor_tags), set(grain.flavor_tags)
    shared = tuple(sorted(source_tags & grain_tags))
    similarity = Fraction(len(shared), len(source_tags | grain_tags)) if source_tags and grain_tags else None
    if not grain_tags:
        review.append(MatchReview('grain_flavor_tags_missing', grain.revision_id))
    gap = None
    if source.color is None:
        review.append(MatchReview('source_color_missing', source.revision_id))
    if grain.color is None:
        review.append(MatchReview('grain_color_missing', grain.revision_id))
    if source.color is not None and grain.color is not None:
        if (source.color.unit, source.color.basis) == (grain.color.unit, grain.color.basis):
            # Interval distance uses fractions before arithmetic; no rounded midpoint.
            gap = max(Fraction(), Fraction(source.color.low) - Fraction(grain.color.high),
                      Fraction(grain.color.low) - Fraction(source.color.high))
        else:
            review.append(MatchReview('color_basis_or_unit_differs', grain.revision_id))
    ranked = bool(similarity) or gap is not None
    if not ranked:
        review.append(MatchReview('no_similarity_evidence', grain.revision_id))
    return GrainMatch('grain:' + grain.revision_id, 'variation' if ranked else 'unranked_variation',
                      (MatchedGrain(grain, Decimal('1')),), shared, similarity, gap, _reviews(review))


def rank_grain_matches(source: CatalogRevision, grains: tuple[CatalogRevision, ...],
                       include_variations: bool = False) -> GrainMatches:
    """Keep reported/assumed composition first without inferring an unknown bill.

    Optional single-grain variations use declared descriptor/color evidence only.
    No candidate is sized; recovery and whole-recipe feasibility still need review.
    A caller selects the supplied revisions; this function does not choose latest.
    """
    _profile(source, 'source')
    if source.kind not in ('dme', 'lme'):
        raise MatchingInputError('source.kind', 'Select a dry or liquid malt extract revision.')
    if type(include_variations) is not bool:
        raise MatchingInputError('include_variations', 'Choose whether to include optional variations.')
    if not isinstance(grains, tuple) or len(grains) > 1000:
        raise MatchingInputError('grains', 'Supply up to 1000 immutable grain revisions.')
    revisions = {source.revision_id}
    product_kinds = {source.product_id: source.kind}
    product_numbers = {(source.product_id, source.revision_number)}
    indexed = {}
    for index, grain in enumerate(grains):
        path = f'grains[{index}]'
        _profile(grain, path)
        if grain.kind != 'grain':
            raise MatchingInputError(path + '.kind', 'Candidate revisions must be grain.')
        if grain.revision_id in revisions:
            raise MatchingInputError(path + '.revision_id', 'Supply each immutable revision once.')
        if grain.product_id in product_kinds and product_kinds[grain.product_id] != grain.kind:
            raise MatchingInputError(path + '.product_id', 'One product identity cannot change fermentable kind.')
        key = (grain.product_id, grain.revision_number)
        if key in product_numbers:
            raise MatchingInputError(path + '.revision_number', 'One product revision number identifies one immutable revision.')
        revisions.add(grain.revision_id)
        product_kinds[grain.product_id] = grain.kind
        product_numbers.add(key)
        indexed[grain.revision_id] = grain

    review = [MatchReview('recovery_required'), MatchReview('mash_feasibility_review'), MatchReview('whole_recipe_review')]
    review.extend(_potential_review(source, source=True))
    if not source.flavor_tags:
        review.append(MatchReview('source_flavor_tags_missing', source.revision_id))
    if source.color is None:
        review.append(MatchReview('source_color_missing', source.revision_id))
    if not indexed:
        review.append(MatchReview('grain_catalogue_empty'))
    if source.composition_status == 'unknown':
        review.append(MatchReview('source_composition_unknown', source.revision_id))
    elif source.composition_status == 'manual_assumption':
        review.append(MatchReview('source_composition_assumed', source.revision_id))

    options = []
    missing = tuple(item.grain_revision_id for item in source.components if item.grain_revision_id not in indexed)
    review.extend(MatchReview('composition_grain_missing', key) for key in missing)
    if source.components and not missing:
        components = tuple(MatchedGrain(indexed[item.grain_revision_id], item.mass_fraction) for item in source.components)
        reasons = [MatchReview('blend_color_unassessed')]
        for item in components:
            reasons.extend(_potential_review(item.revision))
        relation = 'manufacturer_composition' if source.composition_status == 'manufacturer' else 'assumed_composition'
        options.append(GrainMatch('source-composition', relation, components, (), None, None, _reviews(reasons)))

    if include_variations:
        # A single-component composition already supplies that exact grain option.
        retained = {options[0].components[0].revision.revision_id} if options and len(options[0].components) == 1 else set()
        variations = [_variation(source, grain) for key, grain in indexed.items() if key not in retained]
        variations.sort(key=lambda item: (
            item.relation == 'unranked_variation', item.tag_similarity is None,
            -(item.tag_similarity or Fraction()), item.color_gap is None,
            item.color_gap or Fraction(), item.components[0].revision.revision_id,
        ))
        options.extend(variations)
    return GrainMatches(source, tuple(options), _reviews(review))
