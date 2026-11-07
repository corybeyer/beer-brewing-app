# Acceptance scenarios and validation rules

Status: target requirements. These are not claims of implemented behavior or passing tests. Adapted from the supplied October design reference; see [provenance](../references/README.md). [Current status](../plan/status.md) tracks actual evidence.

## Enforcement strategy

Use PostgreSQL foreign keys, uniqueness, NOT NULL, and CHECK constraints for local invariants, per [ADR-0003](../architecture/decisions/0003-postgresql-foundation.md). Use application validation inside transactions for cross-record rules, dependency graph checks, version publication, and state transitions. Database triggers may reinforce immutable history during implementation.

Atomic operations: publish a recipe, instantiate a batch, confirm an action and schedule dependent reminders, apply corrections, and change sensor assignment. Failed validation must leave no partial changes.

## Required integrity rules

| Rule | Enforcement and expected behavior |
|---|---|
| Same recipe version | Recipe additions, dependencies, and anchors cannot reference ingredients/steps from another version. |
| Same batch | Batch additions, action references, dependencies, routes, measurements, and sensor assignments cannot cross batches. |
| Version provenance | Source ingredient/step references must belong to the selected recipe version. Originating tasting must belong to originating batch. |
| Valid routes | Route endpoints belong to the equipment profile; copied batch role endpoints must exist in its saved equipment snapshot. Step route keys must resolve in the selected profile before brewing. |
| No cycles | Check timing anchors and dependencies together. Reject self-dependencies and cycles. |
| Stable versions | Unique recipe_id/version_number. Published versions and their child records cannot be edited; create a draft revision. |
| Preserve history | Batch execution uses copies, not mutable source settings. No cascade deletion that removes retained batch history. |
| Explicit corrections | Append corrections referencing the original event. Store occurrence time separately from recording time. |
| Consistent snapshots | Snapshot and copied batch rows are created together; they preserve source details, targets, style, instructions, ingredient specifications, and equipment. |
| Defined JSON | Validate all JSON fields against documented schemas; arbitrary blobs do not satisfy a required field. |
| Valid quantities | Ingredient quantities positive; timings and tolerances nonnegative except explicitly supported relative offsets; validate alpha acid percentages and unit categories. |
| Defined values | Controlled status, stage, action, trigger, source, purpose, fluid, and unit values. Tasting rating 1–5 when supplied. Allow incomplete drafts; prevent invalid publication/start. |
| Optional readings | Missing actual measurements remain NULL; never replace absence with zero or fabricate readings. |
| Defined volume targets | Distinguish fermenter, kettle, and packaged-volume targets. Compare matching purposes and compatible units. |

## Brew-session behavior

- Starting a session opens the guide; it does not imply heat, pumps, grain addition, or rolling boil.
- Start clocks from confirmed actions; store actual start times and deadlines in UTC, display in user timezone.
- Restore timers from persisted timestamps after refresh/restart. Elapsed downtime counts unless the specific timer was explicitly paused.
- Timed hop reminders relate to confirmed boil start. Changes to boil duration require explicit schedule recalculation/review.
- A temperature target being reached may generate a reminder but cannot confirm an ingredient addition or physical stage change.
- Acknowledging or snoozing a reminder is separate from completing its action.
- Concurrent confirmations from phone/tablet must be idempotent and cannot schedule duplicate additions/alerts.
- Completing one step does not automatically complete unrelated parallel steps.
- Late additions preserve planned and actual timing. Do not silently rewrite earlier physical actions.
- Correcting a timing anchor requires controlled recalculation of pending reminders, with already recorded events preserved.
- Validate planned ingredient portions against recipe quantities; avoid counting one ingredient twice. Log actual portion quantities in addition-event payloads.
- Manual pump/burner status is labeled brewer-confirmed; graphics do not imply direct sensing or remote control.

## Sensor and measurement behavior

- Store measured_at and received_at separately, including sensor assignment/calibration context.
- Classify missing, stale, questionable, and valid readings. Missing is a derived state when no usable record exists.
- Validate vessel, measurement purpose, units, plausible values, and timestamps. Flag suspect data instead of using it silently.
- Sensor assignment changes preserve effective intervals. Late-arriving readings must resolve against the assignment active when measured.
- Manual input works without a sensor and is labeled manual. It can support a recommendation after entry; it does not provide continuous temperature detection.
- Snapshot calibration; determine a documented raw-versus-corrected value policy before integration.
- A disconnected sensor never implies temperature is zero or the equipment is off.

## Meaningful acceptance scenarios

| ID | Scenario | Pass condition |
|---|---|---|
| AC-01 | Cross-version hop link | Reject without saving partial data. |
| AC-02 | Circular mash/transfer dependency | Reject with a clear explanation. |
| AC-03 | Published recipe edit | Create new draft; existing batch retains original plan. |
| AC-04 | Equipment/profile change | Existing batch graphic and settings remain historically accurate. |
| AC-05 | Late boil confirmation | All scheduled additions anchor to actual confirmed start. |
| AC-06 | Phone refresh/server restart | Same remaining times, steps, and reminder statuses recover. |
| AC-07 | Two devices confirm one addition | One authoritative event and one downstream transition. |
| AC-08 | Missing/stale sensor | Display state clearly; no invalid temperature-driven advice. |
| AC-09 | Manual kettle reading | Timestamped measurement with correct vessel/purpose, no fabricated continuous readings. |
| AC-10 | Correct accidental confirmation | Original event remains; effective state and pending alerts reconcile. |
| AC-11 | Ingredient substitution | Original recipe stays unchanged; batch shows substituted actual ingredient. |
| AC-12 | Several tastings | Chronology and age derive correctly; recipe revision links to selected tasting. |
| AC-13 | Recipe import with missing fields | Save reviewable draft; do not silently invent values or mark ready. |
| AC-14 | Backup restoration | Restore recipes, batch copies, actions, readings, tastings, and pending reminder state. |

## Implementation review gate

Before declaring the schema ready, create SQL migrations, document required/optional fields and JSON schemas, verify foreign-key coverage, define allowed state transitions, and run the relevant acceptance scenarios above. This document does not claim those checks have passed.
