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

M2 has [recipe-plan validation](../requirements/recipe-plan-validation.md) and local [draft persistence](../architecture/recipe-draft-storage.md): six recipe tables, composite ownership constraints, exact quantities, and transactional create/load/replace with optimistic editing (UI-02/UI-04/UI-05, storage coverage toward AC-01/AC-02). Source now includes the explicit baseline/recipe deployment compatibility policy, concurrent-write snapshot backups, and a guarded installed-operations updater under proposed ADR-0010. The administrator updated installed operations from the reviewed PR commit before merge; all eight main CI jobs and automatic deployment passed. The [v1 draft overview contract](../../packages/communications/contracts/recipes/v1/README.md) and manual name/description editor merged in PR #11 at `6748d84670bbef09a727901b777ae12040e63d88`, with preserved input and explicit stale-edit review. PR #12 merged the creation-retry pagination fix as `51dd036bb1d1be7dc7a54fe077f9b3d8fee1ee6f`. PR #13 merged ingredient editing and PR #15 merged its request-budget correction. PR #14 merged the sourced conversion core/plan at `e2edd1e3826b5c5f4b01630314409fafb28f321a`. C2a merged/deployed in PR #16 at `7ea325f9017d7df81dbbe7f949ad05b29e750a62` after the reviewed operations update; main CI, live schema/health, and a fresh snapshot restore passed. PR #17 merged the first C2b pure snapshot/review contract at `5c3bfd5196dca352cc424ae6a788097f78bd7df0`; transactional retention remains in draft PR #18. PR #19 merged grain ranking and selected-blend sizing at `1af3ad9`; proposal integration and the picker remain future work; recipe step editing and publication remain outstanding M2 work. See [host evidence](status.md#verified-production-recipe-schema-adoption). Publication/revision rules, classification, targets, and full AC-01–AC-03 acceptance remain owning-feature work.

Use the archived prototype to study behavior and acceptance examples. Port one capability at a time into the chosen boundaries rather than replacing root `app.py` or copying the single-file UI wholesale.

## Definition of done for an implementation task

- Cite the milestone, relevant requirements/screens/scenarios, and applicable ADRs.
- Implement success and failure behavior with meaningful tests; use deterministic simulations before real brewery hardware.
- Run affected checks, and record actual outcomes including skipped/unverified behavior. A new client instance is not proof of process-restart recovery; sequential duplicates are not proof of concurrent idempotency.
- Verify browser accessibility/responsiveness when changing UI, and container/health compatibility when changing runtime or packaging.
- Update [status](status.md), affected specifications, and decisions in the same change. Keep user data and credentials outside source and replaceable containers.

## Planned extract-to-grain conversion

The [sourced conversion and calculator plan](extract-conversion.md) owns the agreed closest-match-first picker, optional flavor variations, preview/apply behavior, original-record retention, formulas, reference assumptions, and CV-01–CV-12 acceptance checks. It links all brewer-supplied sites and distinguishes product yields and mash/brewhouse recovery rather than copying a universal conversion ratio.

C1 merged in PR #14. C2a [catalogue schema/adapter](../architecture/fermentable-catalogue.md) merged/deployed in PR #16 with verified operations, CI, host adoption, and snapshot restore. PR #17 merged the first C2b [pure proposal snapshot contract](../requirements/conversion-proposal-snapshots.md) at `5c3bfd5196dca352cc424ae6a788097f78bd7df0`. Transactional proposal retention/schema remains in draft PR #18. Grain ranking and selected-blend sizing merged in PR #19; the standalone calculator is on `feat/conversion-calculator`. Versioned proposal integration and picker/apply remain separate reviewable slices. [Current delivery gates](delivery-gates.md) records exact branch revisions, successful checks, and the administrator prerequisite for the proposal schema. This supports M2 ingredient planning and M6 reviewed adaptations; recipe step editing/publication and full AC-01–AC-03 remain outstanding. PR #13's ingredient API/editor passed PR CI #29 and merged at `1a92b533109c3044ad63cb8f52fa161b52593f7f`; PR #15 carries its request-budget review follow-up. No current deployment is inferred from the merge/CI evidence.

The first C3 [grain-ranking and exact selected-blend sizing domain slice](../requirements/fermentable-matching.md) merged in PR #19: retain complete reported/assumed compositions first, keep optional variations separate, expose exact descriptor/color evidence and missing-data review, and size explicit grain shares with retained yield/recovery assumptions. This does not depend on proposal persistence and adds no API/UI or schema. The current C2b snapshot format retains one-to-one results only; blend proposal integration and explicit picker/apply remain later work.
