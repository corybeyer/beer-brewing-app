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

PR #10 first adopted the recipe draft schema on the Pi. Liveness, schema readiness, frontend serving, the daily backup timer, and a post-migration snapshot backup/restore were verified for that release. Controlled host recovery and whole-host/off-device restoration remain open under D-06/AC-14.

M2 has [recipe-plan validation](../requirements/recipe-plan-validation.md) and local [draft persistence](../architecture/recipe-draft-storage.md), with version-local links, exact quantities, and transactional edits under a shared revision (UI-02/UI-04/UI-05, AC-01/AC-02). PRs #11–#15 added overview and ingredient editing and corrected creation retry and request limits. PRs #14/#16–#19 delivered conversion calculations, catalogue, proposal retention, and matching. PR #21 added the C4 one-grain conversion picker and atomic Apply. PR #22 added ordered step editing. PR #23 merged optional source, tags, and volume targets with migration `0005_recipe_details`. See [current status](status.md) for verification and release evidence.

The current slice exposes [ingredient portions on steps](../requirements/recipe-plan-validation.md#ingredient-portions-on-steps) through the existing step API and editor. It reuses the current database schema. Gravity targets, BJCP classification and search, publication and version rules, and full AC-01–AC-03 acceptance remain open.

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

The first C3 [grain-ranking and exact selected-blend sizing domain slice](../requirements/fermentable-matching.md) merged in PR #19. The C4 one-grain picker/API/atomic Apply is in PR #21. C3-ranked options, optional variations, blends, and step adaptation remain separate work.
