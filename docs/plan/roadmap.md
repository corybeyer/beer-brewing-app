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

M2 has [recipe-plan validation](../requirements/recipe-plan-validation.md) and local [draft persistence](../architecture/recipe-draft-storage.md): six recipe tables, composite ownership constraints, exact quantities, and transactional create/load/replace with optimistic editing (UI-02/UI-04/UI-05, storage coverage toward AC-01/AC-02). Source now includes the explicit baseline/recipe deployment compatibility policy, concurrent-write snapshot backups, and a guarded installed-operations updater under proposed ADR-0010. The administrator updated installed operations from the reviewed PR commit before merge; all eight main CI jobs and automatic deployment passed. The [v1 draft overview contract](../../packages/communications/contracts/recipes/v1/README.md) and manual name/description editor merged in PR #11 at `6748d84670bbef09a727901b777ae12040e63d88`, with preserved input and explicit stale-edit review. PR #12 merged the creation-retry pagination fix as `51dd036bb1d1be7dc7a54fe077f9b3d8fee1ee6f`. The ingredient API/editor slice is in development with exact amounts and preserved plan references; complete its checks and review. Step editing follows, then publication. See [host evidence](status.md#verified-production-recipe-schema-adoption). Publication/revision rules, classification, targets, and full AC-01–AC-03 acceptance remain owning-feature work.

Use the archived prototype to study behavior and acceptance examples. Port one capability at a time into the chosen boundaries rather than replacing root `app.py` or copying the single-file UI wholesale.

## Definition of done for an implementation task

- Cite the milestone, relevant requirements/screens/scenarios, and applicable ADRs.
- Implement success and failure behavior with meaningful tests; use deterministic simulations before real brewery hardware.
- Run affected checks, and record actual outcomes including skipped/unverified behavior. A new client instance is not proof of process-restart recovery; sequential duplicates are not proof of concurrent idempotency.
- Verify browser accessibility/responsiveness when changing UI, and container/health compatibility when changing runtime or packaging.
- Update [status](status.md), affected specifications, and decisions in the same change. Keep user data and credentials outside source and replaceable containers.

## Planned extract-to-grain conversion

Brewer direction agreed November 8, 2026: suggest the closest grain-bill match to an extract recipe first. Offer an expandable **Explore flavor variations** group in the same picker, with alternatives secondary to the closest match. Each option should show grain names/amounts, expected flavor and color contributions, differences from the closest match, and whether the match uses known manufacturer composition or inferred assumptions. Selection opens a preview; an explicit **Apply to draft** action applies the reviewed proposal while retaining the original extract recipe for comparison.

This is planned work, not an implemented conversion. It needs typed DME/LME/product information, sourced local ingredient characteristics and extract yields, a declared mash/system efficiency basis, and recipe target/volume support. Do not infer an exact dark-extract blend from color alone. Keep added specialty grains distinct from those already included in the extract. Preserve the original amounts, units, product identity, assumptions, and source provenance. Follow the [AHA conversion guidance](https://homebrewersassociation.org/how-to-brew/working-with-extract-recipes/) and manufacturer product information; matching gravity does not establish identical flavor. Scope the deterministic conversion rules and catalogue before implementing recommendations; this extends the M2 ingredient foundation and M6 reviewed adaptation work.
