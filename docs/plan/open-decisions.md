# Decisions and unresolved questions

These items prevent future tasks from silently turning reference examples into product decisions. Proposed options may guide discussion; implementation should record the chosen architecture in an ADR.

## Reconciled context

| Topic | Working baseline | Source/rationale |
| --- | --- | --- |
| Host | Raspberry Pi 5, 16 GB, SSD; port 8080 | Newer repository baseline supersedes the reference's Pi 4 and prototype port 8000 |
| Organization | Use `apps/`, concern-specific `packages/`, categorized `tests/`, `infrastructure/`, and `scripts/` per ADR-0005 | Brewer clarified the intended separation of concerns on November 7, 2026 |
| Product scope | Local advisory app; manual physical actions and confirmations | Consistent across repository, reference, and user-supplied go-bys |
| Prototype role | Behavior reference; not the integrated runtime | Root service remains the existing health foundation |
| Mash equipment | Insulated cooler mash tun; no mash recirculation, HERMS, or RIMS | Brewer clarification on November 7, 2026; sparging and transfer routes remain separate choices |

## Open choices

| ID | Choice | Existing direction and what must be settled | Needed by |
| --- | --- | --- | --- |
| D-01 | Backend architecture and entrypoint | Resolved by accepted ADR-0001 and [ADR-0003](../architecture/decisions/0003-postgresql-foundation.md): FastAPI modular monolith, `brewery_api` in `apps/api`, `brewery_api.api:create_app` factory (ADR-0005); root smoke service retained. | M1 |
| D-02 | Frontend stack and design tooling | Resolved by accepted ADR-0002/ADR-0005: React/TypeScript/Vite, npm workspaces, system fonts, Lucide icons, typed/runtime-validated v1 readiness adapter, shared UI/design-system packages, and Playwright/axe visual and accessibility checks. | M1 |
| D-03 | Persistence and contracts | Tooling resolved by [ADR-0003](../architecture/decisions/0003-postgresql-foundation.md): PostgreSQL 17, SQLAlchemy, Psycopg, and repository-owned Alembic migrations. Feature JSON schemas, controlled values, publication/start transitions, units, target-volume meanings, and field optionality remain open for M2. | M1/M2 |
| D-04 | Timing and notification semantics | Define per-timer pause/resume, late actions, corrections, schedule recalculation, acknowledgement/snoozing, and the background delivery channel. Verify locked-phone/closed-browser behavior separately. | M3 design; M4 completion |
| D-05 | Sensors and equipment routes | Select probes, gateway/protocol, frequency, freshness thresholds, plausibility rules, calibration policy, assignment intervals, Wi-Fi reach, and sparging/transfer routes. Cooler mash tun and no recirculation are settled. MQTT is optional pending sensor selection. | M5 |
| D-06 | Recovery and retention | Proposed ADR-0008 supplies a root-private local baseline: daily and pre-deploy verified PostgreSQL dumps, seven retained sets, and credential copies. Off-device storage, concurrent-write snapshots, long-term retention, and whole-host recovery remain open. JSON export alone is not a restore mechanism. | M1 adoption/M4 |
| D-07 | Access and concurrent use | Define trusted-LAN access/authentication needs and simultaneous-device behavior before extending exposure. Preserve server authority and idempotent actions. | M3/M4 |
| D-08 | Imports and comparisons | Choose supported text/file/URL modes, parsing/OCR/AI services and any network needs; attribution/original retention; missing-field review and unit-compatible comparison rules. | M6 |

## Decision record process

Use [decision records](../architecture/decisions/README.md) for architectural choices. Record context, status, chosen option, consequences, and affected requirements. Mark this table resolved with an ADR link only after the choice is explicit. Approval of documentation does not automatically accept every proposed framework or roadmap detail.
