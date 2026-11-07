# Decisions and unresolved questions

These items prevent future tasks from silently turning reference examples into product decisions. Proposed options may guide discussion; implementation should record the chosen architecture in an ADR.

## Reconciled context

| Topic | Working baseline | Source/rationale |
| --- | --- | --- |
| Host | Raspberry Pi 5, 16 GB, SSD; port 8080 | Newer repository baseline supersedes the reference's Pi 4 and prototype port 8000 |
| Organization | Retain `app/`, `web/`, `contracts/`, `infra/`, `docs/`, and `tests/` boundaries | User prefers the newer structure; existing agent instructions describe responsibilities |
| Product scope | Local advisory app; manual physical actions and confirmations | Consistent across repository, reference, and user-supplied go-bys |
| Prototype role | Behavior reference; not the integrated runtime | Root service remains the existing health foundation |
| HERMS | Undecided | Reference explicitly corrects the illustrated coil |

## Open choices

| ID | Choice | Existing direction and what must be settled | Needed by |
| --- | --- | --- | --- |
| D-01 | Backend architecture and entrypoint | FastAPI modular monolith is the target direction; ADR-0001 remains Proposed. Define domain/service/adapter boundaries and avoid ambiguity between `app.py` and `app/`. | M1 |
| D-02 | Frontend stack and design tooling | Repository proposes React/TypeScript and shared components; prototype is plain HTML/JS. Decide framework/build tooling, API client generation approach, icons, typography, and visual checks; ADR-0002 remains Proposed. | M1 |
| D-03 | Persistence and contracts | SQLite is the initial target; SQLAlchemy/Alembic are proposed repository tooling. Define migration ownership, JSON schemas, controlled values, publication/start transitions, units, target-volume meanings, and field optionality. | M1/M2 |
| D-04 | Timing and notification semantics | Define per-timer pause/resume, late actions, corrections, schedule recalculation, acknowledgement/snoozing, and the background delivery channel. Verify locked-phone/closed-browser behavior separately. | M3 design; M4 completion |
| D-05 | Sensors and equipment routes | Select probes, gateway/protocol, frequency, freshness thresholds, plausibility rules, calibration policy, assignment intervals, Wi-Fi reach, and whether HERMS is used. MQTT is optional pending this choice. | M5 |
| D-06 | Recovery and retention | Decide backup location/schedule, consistent SQLite backup approach, restore procedure, retention, and recovery expectations. JSON export alone is not a restore mechanism. | M4 |
| D-07 | Access and concurrent use | Define trusted-LAN access/authentication needs and simultaneous-device behavior before extending exposure. Preserve server authority and idempotent actions. | M3/M4 |
| D-08 | Imports and comparisons | Choose supported text/file/URL modes, parsing/OCR/AI services and any network needs; attribution/original retention; missing-field review and unit-compatible comparison rules. | M6 |

## Decision record process

Use [decision records](../decisions/README.md) for architectural choices. Record context, status, chosen option, consequences, and affected requirements. Mark this table resolved with an ADR link only after the choice is explicit. Approval of documentation does not automatically accept every proposed framework or roadmap detail.
