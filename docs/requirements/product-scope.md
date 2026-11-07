# Product scope

Status: target requirements consolidated from the supplied design reference and wireframes. See [current status](../plan/status.md) for implementation evidence and [open decisions](../plan/open-decisions.md) for unresolved details.

## Purpose and equipment

Build a locally hosted, advisory companion for five-gallon all-grain batches. The brewer uses a responsive browser on a phone, tablet, or computer on the home network. The repository's current host baseline is Raspberry Pi 5 with 16 GB RAM and SSD; the older reference's Pi 4 is historical.

Equipment direction: HLT, mash tun, and boil kettle; outdoor propane; two burners; two pumps; manually operated heating, switches, valves, and hoses; immersion chilling. HERMS remains undecided. Do not derive a selected route from the coil shown in the dashboard mockup.

The app monitors, records, and advises. Physical equipment control is outside the initial scope. Reaching a temperature or timer deadline never proves a physical action occurred.

## User journey

1. Create or revise a recipe, choose a style or Custom, enter ingredients, targets, and every ordered brewing step.
2. Review and publish a usable recipe version. Preserve source attribution. Imported material must be reviewed before publication.
3. Prepare a batch with a snapshot of that recipe and the equipment settings, readiness checks, substitutions, and planned volumes.
4. Follow the brew-day guide, explicitly confirming actions and stage transitions. Run hold timers and parallel addition reminders from confirmed anchors.
5. Record manual measurements, actual ingredient use, notes, times, and deviations; integrate sensors in a later milestone.
6. Review planned versus actual results and the brew log. Add repeated tastings as the beer ages.
7. Create a draft recipe revision from selected feedback while preserving the original recipe version, batch, and tasting history.

## Required capabilities

| Capability | Intended behavior |
| --- | --- |
| Recipes | Manual creation and experimentation; draft/published versions; ingredients, portions, targets, ordered steps, dependencies, equipment instructions, and timing anchors |
| Classification | Searchable BJCP guideline edition/code and Custom; free-text names/tags; source independent of style; style ranges are guidance, not mandatory limits |
| Batch setup | Recipe/equipment review, preparation checklist, substitutions, input-source selection, and immutable historical snapshots |
| Brew-day guide | Current instructions, all steps, vessel readings/targets, persistent timers, upcoming reminders, trend displays, and planned equipment graphics |
| Confirmations | Explicit brewer confirmation; idempotent concurrent requests; alert acknowledgement separate from physical completion |
| Measurements | Vessel, purpose, unit, measured/received timestamps, source, and quality; manual entry works without sensors; absence stays absent |
| History | Planned/actual ingredient use and measurements, corrections that retain original events, batch review, multiple tastings, and revision provenance |
| Recovery | Server-owned deadlines and state survive browser closure and service restart; database backup and restoration preserve the complete workflow |
| Imports | Preserve originals and attribution; show extraction issues; require review; specific parsers/OCR/AI capabilities remain undecided |

Data and transition rules are specified in [acceptance scenarios](acceptance-scenarios.md) and the [target data model](../architecture/data-model.md). Screen behavior is described in [screen specifications](../design/screens.md).

## Trust and timing

The server owns session state and timer deadlines in UTC; presentation uses the user's timezone. Closing the browser does not pause a brew. Pausing a particular timer requires explicit semantics and never means physical brewing has stopped.

Manual readings support advice after validated entry but cannot detect changes between entries. Sensor readings must distinguish valid, stale, questionable, and missing data, with measurement provenance. Pump/burner status is brewer-confirmed unless a separately specified sensor actually measures it.

The reference prototype evaluates alerts during dashboard polling. Closed-browser and locked-phone notification delivery require a separate background scheduler/channel and validation; persisted deadlines alone do not provide that capability.

## Delivery scope

The first integrated workflow is a simulated manual brew: recipe version -> batch setup -> timed/confirmed steps -> manual measurements -> review and tastings. Validate it before adding sensors. The roadmap stages reliability, background reminders, sensor integrations, comparisons, and import improvements separately.

Automatic equipment control, public internet hosting, microservices, and an assumed HERMS layout are outside this initial plan. Future scope changes need an explicit decision and updated acceptance criteria.
