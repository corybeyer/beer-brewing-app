# Home Brewery Setup — Project Reference

Design baseline: October 9, 2026 (America/Chicago).
Status: approved design plus first runnable manual prototype (October 10, 2026). Live sensors and the full production ERD are not implemented.

## Start here in a future session

Read this file, decisions-and-scope.md, database/current-erd.md, and validation-requirements.md before proposing or implementing changes. This package is the consolidated reference for the app design. The corrected three-part ERD supersedes the earlier single ERD.

Do not infer that a feature is implemented because it appears in a wireframe. Mockups contain sample data. Preserve the agreed scope and mark new choices as proposals until accepted.

## Contents

- decisions-and-scope.md: agreed architecture, boundaries, open decisions, and wireframe-to-data coverage.
- database/current-erd.md: latest ERDs with fields and implementation notes.
- database/*.mmd: three editable Mermaid diagram sources.
- validation-requirements.md: integrity rules, workflow validation, and meaningful acceptance scenarios.
- wireframes/: all six app wireframes created in this session.
- PROJECT_REFERENCE.md: consolidated text reference suitable for adding as a Project file.
- manifest.json: file inventory and checksums.

## Wireframes

1. 01-brew-day-dashboard.png — live temperatures, timers, small graphics, current action, and next reminders.
2. 02-recipe-steps.png — ordered steps, timing anchors, ingredient links, and confirmations.
3. 03-batch-review-tastings.png — planned/actual results and repeated tasting records.
4. 04-recipe-library-ingredients.png — recipe search, import proposals, sources, and ingredient entry.
5. 05-recipe-overview-style.png — searchable BJCP classification, editable targets, and tags.
6. 06-batch-setup.png — recipe/equipment review, preparation checks, substitutions, and sensor/manual inputs.

## Important image corrections

- The dashboard includes a HERMS coil. HERMS was explicitly left undecided; replace that route with the chosen equipment layout during implementation.
- The first dashboard has inconsistent step numbering between its header and step strip; final numbers must derive from the batch's actual steps.
- The phone recipe-step mockup omits intermediate steps for illustration; the app must show every step in order.
- Manual readings can support recommendations when entered and validated, but cannot detect a temperature change between entries. The batch-setup phrase “No automatic kettle alerts” means no continuous sensor-triggered detection.
- The batch-review image includes an internal instruction under its revision button. Remove that line from the product UI; creating a revision must preserve history regardless.
- The library's imported-text caption has a rendering defect. Final UI text: “Review extracted ingredients and steps before saving.”
- Import modes are proposed interfaces, not verified website/file parsing capabilities.

## Using this across ChatGPT sessions

Add PROJECT_REFERENCE.md and the six images to the Home Brewery Setup Project's files. The ZIP retains the complete folder structure and editable diagrams. Saving this package does not itself attach it to the ChatGPT Project or guarantee automatic context loading in another chat.


---

# Decisions and scope

## Agreed equipment direction

Five-gallon all-grain batches; three vessels (HLT, mash tun, boil kettle); outdoor propane; two burners; two pumps; manual heating, pump switches, valves, and hose routing; immersion chilling. HERMS remains undecided.

## Agreed app direction

Custom locally hosted app on the user's Raspberry Pi 4 with 4 GB RAM. Responsive browser interface for phone, tablet, and computer on home Wi-Fi. Proposed implementation stack accepted for planning: Python/FastAPI and SQLite.

Server owns session state and timer deadlines. Closing a browser does not stop a brew session. The initial system advises and records; the brewer performs and confirms physical actions.

Recipes support manual creation, personal experiments, and reviewed imports from books or websites. Preserve source attribution and original supplied material. Recipes have ingredients, targets, ordered steps, durations, temperature targets, equipment instructions, additions, and relative reminders.

The brew-day dashboard shows measured temperatures, target temperatures, elapsed/remaining times, temperature trends, small vessel/flow graphics, current instructions, and upcoming actions. Readings and brewer-confirmed equipment status are distinct.

Each batch preserves the recipe version and equipment settings used. Log actual times, ingredient substitutions, measurements, deviations, corrections, and notes. Multiple tastings attach to each batch, with observations, ratings, and suggestions for later recipe revisions.

## Recipe classification

Searchable BJCP dropdown, guideline edition and code preserved. BJCP 2021 18B American Pale Ale is the wireframe example. Allow Unclassified / Custom. Recipe name and personal tags are free text; source is independent of style. Style ranges are references, not enforced limits.

Official reference: https://www.bjcp.org/beer-styles/beer-style-guidelines/
Example style: https://styles.bjcp.org/bjcp-2021-beer/18/18b-american-pale-ale

## Screen-to-data coverage

| Screen/component | Database support |
|---|---|
| Library search, drafts, versions | RECIPE, RECIPE_VERSION |
| Tags and style filters | TAG, RECIPE_TAG, BEER_STYLE |
| Books, websites, personal sources | RECIPE_SOURCE |
| Import originals, draft extraction, review | RECIPE_IMPORT |
| Grain, hops, yeast, additions | RECIPE_INGREDIENT |
| Ingredient portions and schedules | STEP_ADDITION, BATCH_STEP_ADDITION |
| Ordered steps, stages, targets, anchors | RECIPE_STEP, BATCH_STEP |
| Required prior confirmations | STEP_DEPENDENCY, BATCH_STEP_DEPENDENCY |
| Setup dates, batch name, target volume | BATCH |
| Ingredient readiness checkboxes | BATCH_CHECKLIST_ITEM |
| Substitutions and actual quantities | BATCH_INGREDIENT |
| Equipment and planned graphic routes | EQUIPMENT_PROFILE, EQUIPMENT_COMPONENT, FLOW_ROUTE, FLOW_ROUTE_SEGMENT |
| Historical batch routes | BATCH_FLOW_ROUTE, BATCH_FLOW_SEGMENT |
| Equipment action instructions | STEP_EQUIPMENT_ACTION, BATCH_EQUIPMENT_ACTION |
| Manual pump/burner/transfer confirmations | ACTION_EVENT |
| Persistent reminder state | BATCH_ALERT |
| Sensor/manual choices and freshness | SENSOR, BATCH_SENSOR_ASSIGNMENT |
| Temperature trends, gravity, pH, volumes | MEASUREMENT |
| Brew notes and correction history | BATCH, ACTION_EVENT |
| Planned versus actual comparisons | BATCH snapshots, BATCH_INGREDIENT, BATCH_STEP, MEASUREMENT |
| Tasting timeline, beer age, latest rating | TASTING, BATCH.packaged_at |
| Recipe improvement provenance | RECIPE_VERSION parent/version and originating batch/tasting |

## Open implementation choices

- Exact temperature probes, gateway, transport protocol, sampling frequency, stale thresholds, and Wi-Fi reach.
- Frontend framework and visual asset implementation.
- Reliable alert delivery when phone is locked; browser-only display is insufficient as an assumed solution.
- Import parsers, photo/OCR extraction, and any AI assistance; confirm capabilities and whether they need internet access.
- Detailed JSON schemas for brewing targets, specifications, snapshots, and event payloads.
- Unit normalization, enumerations, retention policy, database migrations, backup location, and restore procedure.
- Timer pause semantics: support individual timer pauses explicitly; do not assume pausing the interface pauses physical brewing.

## Build sequence

1. Recipe entry, versioning, steps, and classification — basic manual prototype implemented; full catalog/source schema pending.
2. Manual brew session: timers, confirmations, measurements, batch review, and tasting journal.
3. Temperature sensors and freshness/quality handling.
4. Comparisons and reviewed import enhancements.

Test a simulated brew before integrating sensors. Automatic hardware control is outside the initial scope.


---

# Home Brewery Setup — Current ERDs
Baseline: 2026-10-09 (America/Chicago). Status: agreed design, not an implemented database.
These are the latest three ERDs from the corrected design. Earlier ERDs are superseded. PK = primary key; FK = foreign key. Optional references and cross-view relationships require the rules in validation-requirements.md.

## Recipes and reusable brewing plans

```mermaid
erDiagram
    direction TB

    RECIPE ||--|{ RECIPE_VERSION : has
    BEER_STYLE o|--o{ RECIPE_VERSION : classifies
    RECIPE_VERSION o|--o{ RECIPE_VERSION : revises
    RECIPE ||--o{ RECIPE_TAG : has
    TAG ||--o{ RECIPE_TAG : labels
    RECIPE_VERSION ||--o{ RECIPE_SOURCE : credits
    RECIPE_IMPORT o|--o| RECIPE_VERSION : produces
    RECIPE_VERSION ||--o{ RECIPE_INGREDIENT : contains
    RECIPE_VERSION ||--o{ RECIPE_STEP : defines
    RECIPE_STEP ||--o{ STEP_ADDITION : schedules
    RECIPE_INGREDIENT ||--o{ STEP_ADDITION : supplies
    RECIPE_STEP ||--o{ STEP_DEPENDENCY : requires
    RECIPE_STEP ||--o{ STEP_EQUIPMENT_ACTION : instructs

    RECIPE {
        int id PK
        string name
        datetime created_at
    }

    RECIPE_VERSION {
        int id PK
        int recipe_id FK
        int style_id FK
        int parent_version_id FK
        int originating_batch_id FK
        int originating_tasting_id FK
        int version_number
        string status
        text description
        float batch_volume
        string volume_unit
        json brewing_targets
    }

    BEER_STYLE {
        int id PK
        string guideline
        string edition
        string code
        string name
        text sensory_description
        string reference_url
        json reference_ranges
    }

    TAG {
        int id PK
        string name
    }

    RECIPE_TAG {
        int recipe_id PK,FK
        int tag_id PK,FK
    }

    RECIPE_SOURCE {
        int id PK
        int recipe_version_id FK
        string source_type
        string title
        string author
        string page_reference
        string url
        text notes
    }

    RECIPE_IMPORT {
        int id PK
        string input_type
        text original_text
        string original_file_reference
        string original_url
        json extracted_draft
        json review_issues
        string review_status
        datetime reviewed_at
    }

    RECIPE_INGREDIENT {
        int id PK
        int recipe_version_id FK
        string category
        string name
        float quantity
        string unit
        string intended_use
        float alpha_acid_percent
        json additional_specifications
    }

    RECIPE_STEP {
        int id PK
        int recipe_version_id FK
        int sequence
        string stage
        string title
        string action_type
        text instructions
        string trigger_type
        int anchor_step_id FK
        string anchor_event
        int offset_seconds
        int duration_seconds
        string vessel_role
        float target_temperature
        float temperature_tolerance
        string temperature_unit
        json other_targets
        boolean confirmation_required
    }

    STEP_ADDITION {
        int id PK
        int recipe_step_id FK
        int recipe_ingredient_id FK
        float quantity
        string unit
    }

    STEP_DEPENDENCY {
        int id PK
        int recipe_step_id FK
        int required_step_id FK
        string required_event
    }

    STEP_EQUIPMENT_ACTION {
        int id PK
        int recipe_step_id FK
        string equipment_role
        string requested_action
        string route_key
        boolean confirmation_required
    }
```

## Batch setup, execution, and tasting

```mermaid
erDiagram
    direction TB

    RECIPE_VERSION ||--o{ BATCH : supplies_plan
    EQUIPMENT_PROFILE ||--o{ BATCH : configures
    BATCH ||--o{ BATCH_CHECKLIST_ITEM : prepares
    BATCH ||--o{ BATCH_INGREDIENT : uses
    BATCH ||--o{ BATCH_STEP : executes
    BATCH_STEP ||--o{ BATCH_STEP_ADDITION : schedules
    BATCH_INGREDIENT ||--o{ BATCH_STEP_ADDITION : supplies
    BATCH_STEP ||--o{ BATCH_STEP_DEPENDENCY : requires
    BATCH_STEP ||--o{ BATCH_EQUIPMENT_ACTION : plans
    BATCH ||--o{ ACTION_EVENT : records
    BATCH_STEP o|--o{ ACTION_EVENT : relates
    ACTION_EVENT o|--o{ ACTION_EVENT : corrects
    BATCH_STEP ||--o{ BATCH_ALERT : generates
    BATCH ||--o{ TASTING : receives

    BATCH {
        int id PK
        int recipe_version_id FK
        int equipment_profile_id FK
        string name
        string status
        date planned_brew_date
        float target_volume
        string volume_unit
        json recipe_snapshot
        json equipment_snapshot
        datetime started_at
        datetime brew_completed_at
        datetime packaged_at
        string packaging_method
        text notes
    }

    BATCH_CHECKLIST_ITEM {
        int id PK
        int batch_id FK
        string label
        boolean completed
        datetime completed_at
    }

    BATCH_INGREDIENT {
        int id PK
        int batch_id FK
        int source_recipe_ingredient_id FK
        string planned_name
        float planned_quantity
        string planned_unit
        string actual_name
        float actual_quantity
        string actual_unit
        json specifications_snapshot
        text substitution_notes
    }

    BATCH_STEP {
        int id PK
        int batch_id FK
        int source_recipe_step_id FK
        int sequence
        string stage
        string title
        json step_snapshot
        int anchor_batch_step_id FK
        string anchor_event
        string status
        datetime due_at
        datetime started_at
        datetime timer_deadline
        int paused_seconds
        datetime paused_at
        datetime completed_at
    }

    BATCH_STEP_DEPENDENCY {
        int id PK
        int batch_step_id FK
        int required_batch_step_id FK
        string required_event
    }

    BATCH_STEP_ADDITION {
        int id PK
        int batch_step_id FK
        int batch_ingredient_id FK
        float planned_quantity
        string unit
    }

    BATCH_EQUIPMENT_ACTION {
        int id PK
        int batch_step_id FK
        string equipment_role
        string requested_action
        int batch_flow_route_id FK
        boolean confirmation_required
    }

    ACTION_EVENT {
        int id PK
        int batch_id FK
        int batch_step_id FK
        int batch_step_addition_id FK
        int batch_equipment_action_id FK
        int corrects_event_id FK
        string event_type
        datetime occurred_at
        datetime recorded_at
        json details
    }

    BATCH_ALERT {
        int id PK
        int batch_step_id FK
        string alert_type
        string message
        datetime due_at
        string status
        datetime acknowledged_at
        datetime snoozed_until
    }

    TASTING {
        int id PK
        int batch_id FK
        datetime tasted_at
        text appearance
        text aroma
        text flavor
        text mouthfeel
        text off_flavors
        int rating
        text overall_notes
        boolean would_brew_again
        text next_batch_changes
    }
```

## Equipment, graphics, and measurements

```mermaid
erDiagram
    direction TB

    EQUIPMENT_PROFILE ||--o{ EQUIPMENT_COMPONENT : contains
    EQUIPMENT_PROFILE ||--o{ FLOW_ROUTE : defines
    FLOW_ROUTE ||--|{ FLOW_ROUTE_SEGMENT : follows
    BATCH ||--o{ BATCH_FLOW_ROUTE : preserves
    BATCH_FLOW_ROUTE ||--|{ BATCH_FLOW_SEGMENT : follows
    BATCH_FLOW_ROUTE o|--o{ BATCH_EQUIPMENT_ACTION : illustrates
    BATCH ||--o{ BATCH_SENSOR_ASSIGNMENT : selects
    SENSOR o|--o{ BATCH_SENSOR_ASSIGNMENT : supplies
    BATCH ||--o{ MEASUREMENT : collects
    BATCH_STEP o|--o{ MEASUREMENT : contextualizes
    BATCH_SENSOR_ASSIGNMENT o|--o{ MEASUREMENT : identifies_source

    EQUIPMENT_PROFILE {
        int id PK
        string name
        json brewing_assumptions
    }

    EQUIPMENT_COMPONENT {
        int id PK
        int equipment_profile_id FK
        string role_key
        string component_type
        string name
        json specifications
    }

    FLOW_ROUTE {
        int id PK
        int equipment_profile_id FK
        string route_key
        string name
        string fluid_type
    }

    FLOW_ROUTE_SEGMENT {
        int id PK
        int flow_route_id FK
        int sequence
        int from_component_id FK
        int to_component_id FK
    }

    BATCH_FLOW_ROUTE {
        int id PK
        int batch_id FK
        string route_key
        string name
        string fluid_type
    }

    BATCH_FLOW_SEGMENT {
        int id PK
        int batch_flow_route_id FK
        int sequence
        string from_role
        string to_role
    }

    SENSOR {
        int id PK
        string device_key
        string name
        string measurement_type
        json calibration
    }

    BATCH_SENSOR_ASSIGNMENT {
        int id PK
        int batch_id FK
        int sensor_id FK
        string vessel_role
        string measurement_type
        string input_mode
        int stale_after_seconds
        json calibration_snapshot
        datetime active_from
        datetime active_until
    }

    MEASUREMENT {
        int id PK
        int batch_id FK
        int batch_step_id FK
        int sensor_assignment_id FK
        string measurement_type
        string purpose
        string vessel_role
        float value
        string unit
        string source
        string quality_status
        datetime measured_at
        datetime received_at
    }
```

## Implementation notes

- ERDs are logical design, not SQL DDL. JSON schemas must be defined before implementation.
- Recipe imports produce at most one initial version; track that link with a unique nullable foreign key during implementation.
- Anchor, dependency, originating batch/tasting, and route endpoint references are included as fields; not every edge is drawn to keep the views readable.
- Snapshots preserve targets, instructions, style classification/reference, source details, ingredient specifications, and equipment configuration.
- Batch tables are authoritative for execution; published recipe versions are immutable.
- Route graphics depict planned fluid paths; confirmed equipment states come from action events. HERMS is not selected.
- Temperature freshness, timers, beer age, ratings, and comparisons are derived from stored values/timestamps.
- Successful alert acknowledgement is distinct from confirming its physical action.


---

# Database and workflow validation requirements

Status: requirements and acceptance plan, not implemented or executed tests.

## Enforcement strategy

Use foreign keys, uniqueness, NOT NULL, and CHECK constraints for local invariants. Enable SQLite foreign-key enforcement on every connection. Use application validation inside transactions for cross-record rules, dependency graph checks, version publication, and state transitions. Database triggers may reinforce immutable history during implementation.

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

| Scenario | Pass condition |
|---|---|
| Cross-version hop link | Reject without saving partial data. |
| Circular mash/transfer dependency | Reject with a clear explanation. |
| Published recipe edit | Create new draft; existing batch retains original plan. |
| Equipment/profile change | Existing batch graphic and settings remain historically accurate. |
| Late boil confirmation | All scheduled additions anchor to actual confirmed start. |
| Phone refresh/server restart | Same remaining times, steps, and reminder statuses recover. |
| Two devices confirm one addition | One authoritative event and one downstream transition. |
| Missing/stale sensor | Display state clearly; no invalid temperature-driven advice. |
| Manual kettle reading | Timestamped measurement with correct vessel/purpose, no fabricated continuous readings. |
| Correct accidental confirmation | Original event remains; effective state and pending alerts reconcile. |
| Ingredient substitution | Original recipe stays unchanged; batch shows substituted actual ingredient. |
| Several tastings | Chronology and age derive correctly; recipe revision links to selected tasting. |
| Recipe import with missing fields | Save reviewable draft; do not silently invent values or mark ready. |
| Backup restoration | Restore recipes, batch copies, actions, readings, tastings, and pending reminder state. |

## Implementation review gate

Before declaring the schema ready, create SQL migrations, document required/optional fields and JSON schemas, verify foreign-key coverage, define allowed state transitions, and run the relevant acceptance scenarios above. This document does not claim those checks have passed.


---

# Implementation checkpoint — October 10, 2026

The first FastAPI/SQLite prototype is saved as brewery-app-prototype.zip. It includes a responsive web UI, recipe drafts/publication/revisions, batch setup, manual readings, persisted timers, parallel boil reminders, confirmations, notes, batch review, repeated tastings, and JSON export.

The prototype uses eight compact SQLite tables and validated snapshots. The 31-entity ERD above is still the target production design, not a claim of completed migrations. Prototype limitations and Pi startup instructions are in the archive README.md.

Four backend tests and a DOM integration workflow passed. Visual browser testing was blocked by the failed Chromium download; real Pi and sensor trials remain pending. Never imply that closed-browser or locked-phone alerts work: alerts are currently evaluated by dashboard polling.

Next: run the manual trial on the Pi, check the approved layouts at phone/tablet widths, then implement the full relational schema, correction controls, and background scheduler before sensor integration.
