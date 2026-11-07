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

The backend/persistence portion of M1 now has an isolated FastAPI/PostgreSQL foundation under [ADR-0003](../architecture/decisions/0003-postgresql-foundation.md). The frontend preview and workspace boundaries follow ADR-0002/ADR-0005. PR #6's container checks passed and its retained smoke image deployed successfully after main CI. A separate [UI/API candidate](../../infrastructure/docker/README.md) now implements same-origin port 8080 serving under proposed ADR-0007, with 18 native host browser checks passing against a real API/database. Next review candidate-container and ARM64 CI evidence, then explicitly settle the [production adoption gates](../../infrastructure/deployment/production/README.md), including stateful operations and controlled rollback, before replacing the smoke service. The API entrypoint is `brewery_api.api:create_app`, with separate UI/design-system/database/configuration/communications owners. Feature contracts and business-table migrations remain owning-feature work.

Use the archived prototype to study behavior and acceptance examples. Port one capability at a time into the chosen boundaries rather than replacing root `app.py` or copying the single-file UI wholesale.

## Definition of done for an implementation task

- Cite the milestone, relevant requirements/screens/scenarios, and applicable ADRs.
- Implement success and failure behavior with meaningful tests; use deterministic simulations before real brewery hardware.
- Run affected checks, and record actual outcomes including skipped/unverified behavior. A new client instance is not proof of process-restart recovery; sequential duplicates are not proof of concurrent idempotency.
- Verify browser accessibility/responsiveness when changing UI, and container/health compatibility when changing runtime or packaging.
- Update [status](status.md), affected specifications, and decisions in the same change. Keep user data and credentials outside source and replaceable containers.
