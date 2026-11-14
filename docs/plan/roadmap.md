# Development roadmap

Status: proposed delivery sequence based on the supplied reference and current repository. Milestones are not completed merely because similar behavior exists in the archived prototype. [Current status](status.md) tracks evidence; [open decisions](open-decisions.md) records unresolved choices.

## Milestones and completion criteria

| ID | Milestone | Depends on | Completion evidence |
| --- | --- | --- | --- |
| M0 | Repository knowledge base | Existing foundation | Linked scope, architecture, design guidance, acceptance scenarios, provenance, and status; image availability disclosed |
| M1 | Application foundation | M0; D-01, D-02, D-03 | Runnable backend/UI/persistence foundation in the retained structure; migrations and test isolation; `/health` preserved; container and deployment compatibility checked |
| M2 | Recipe planning and versions | M1 | Manual recipe entry, classification, ingredients, step/portion/dependency editing, publication and revisions; AC-01–AC-03; UI-02, UI-04, UI-05 checks |
| M3 | Simulated manual brew through tasting | M2 | Batch setup/snapshots, server-owned timers, confirmed actions, parallel additions, manual measurements, notes, review and tastings; AC-04–AC-07, AC-09, AC-11, AC-12; UI-01, UI-03, UI-06 checks |
| M4 | Recovery and operational reliability | M3; D-04, D-06, D-07 | Event correction/reconciliation (AC-10), explicit pause/snooze semantics, real restart and concurrent-client tests, backup restoration (AC-14), and separately verified background/locked-phone reminder behavior |
| M5 | Sensor integration | Validated manual simulation and M4; D-05 | Selected hardware/protocol; assignment/calibration history; measured/received timestamps; missing/stale/outlier behavior (AC-08); simulated adapter tests and documented hardware trial results |
| M6 | Comparisons and reviewed imports | M3/M4; D-08 | Meaningful planned/actual and cross-batch comparisons; chosen import modes preserve originals/attribution and require review (AC-13); missing data/unit compatibility checked |

Scenario IDs refer to [acceptance scenarios](../requirements/acceptance-scenarios.md). Screen IDs refer to [screen specifications](../design/screens.md). Decision IDs refer to [open decisions](open-decisions.md).

Build a representative vertical workflow early. Implement relational constraints and versioned migrations alongside the owning feature; do not create every target entity simply to match the ERD. All relevant integrity requirements must be met before declaring the full schema complete.

## Next development task

The Pi now runs the UI/API and six-table recipe draft schema at main commit `2df377693d647aa87ec0b98d5470d78fe93c379c` (PR #10). Liveness, schema readiness, frontend serving, enabled/active daily backup timer, and a fresh post-migration snapshot backup/restore were verified. Controlled host recovery and whole-host/off-device restoration remain distinct outstanding evidence (D-06/AC-14); preserve the retained smoke rollback.

M2 has [recipe-plan validation](../requirements/recipe-plan-validation.md) and local [draft persistence](../architecture/recipe-draft-storage.md): recipe tables, composite ownership constraints, exact quantities, and transactional create/load/replace with optimistic editing (UI-02/UI-04/UI-05, storage coverage toward AC-01/AC-02). Source includes explicit deployment compatibility policies and guarded installed-operations updates under proposed ADRs. The [v1 draft overview contract](../../packages/communications/contracts/recipes/v1/README.md) and manual name/description editor merged in PR #11; PR #12 fixed creation-retry pagination; PRs #13/#15 added ingredient editing and its bounded request correction. PRs #14/#16–#19 delivered sourced conversion, catalogue, proposal retention, and matching slices. PR #21 adds the C4 one-grain conversion picker and atomic Apply. Ordered recipe step editing merged in PR #22 at `74488568d5c8dc6e0040f20d9e1d709d1f00d1ee`; PR CI #48 passed. The current development slice adds optional recipe source, tags, and fermenter/kettle/packaged volume targets with migration `0005_recipe_details`, explicit production rollout compatibility, and shared-revision conflict handling. Gravity targets, BJCP classification/search, publication/version rules, and full AC-01–AC-03 acceptance remain outstanding.

Use the archived prototype to study behavior and acceptance examples. Port one capability at a time into the chosen boundaries rather than replacing root `app.py` or copying the single-file UI wholesale.

## Definition of done for an implementation task

- Cite the milestone, relevant requirements/screens/scenarios, and applicable ADRs.
- Implement success and failure behavior with meaningful tests; use deterministic simulations before real brewery hardware.
- Run affected checks, and record actual outcomes including skipped/unverified behavior. A new client instance is not proof of process-restart recovery; sequential duplicates are not proof of concurrent idempotency.
- Verify browser accessibility/responsiveness when changing UI, and container/health compatibility when changing runtime or packaging.
- Update [status](status.md), affected specifications, and decisions in the same change. Keep user data and credentials outside source and replaceable containers.

## Planned extract-to-grain conversion

The [sourced conversion and calculator plan](extract-conversion.md) owns the agreed closest-match-first picker, optional flavor variations, preview/apply behavior, original-record retention, formulas, reference assumptions, and CV-01–CV-12 acceptance checks. It links all brewer-supplied sites and distinguishes product yields and mash/brewhouse recovery rather than copying a universal conversion ratio.

C1 merged in PR #14. C2a [catalogue schema/adapter](../architecture/fermentable-catalogue.md) merged/deployed in PR #16 with verified operations, CI, host adoption, and snapshot restore. The first C2b [pure proposal snapshot contract](../requirements/conversion-proposal-snapshots.md) merged in PR #17; transactional retention is implemented on schema `0004`. The C3 matching core merged in PR #19. The C4 versioned proposal API, picker, and atomic Apply are in development as described in [current status](status.md#current-work-c4-one-grain-conversion-picker-and-apply). Standalone calculators remain later work. This supports M2 ingredient planning and M6 reviewed adaptations; recipe step editing/publication and full AC-01–AC-03 remain outstanding. PR #13's ingredient API/editor passed PR CI #29 and merged at `1a92b533109c3044ad63cb8f52fa161b52593f7f`; PR #15 carries its request-budget review follow-up. No current deployment is inferred from the merge/CI evidence.

The first C3 [grain-ranking and exact selected-blend sizing domain slice](../requirements/fermentable-matching.md) merged in PR #19. The C4 one-grain picker/API/atomic Apply is in PR #21. It does not yet expose C3-ranked options, optional variations, blends, or step adaptation. Recipe details/volume targets now proceed as a separate M2 slice; see [current status](status.md#current-work-m2-recipe-details-and-volume-targets).
