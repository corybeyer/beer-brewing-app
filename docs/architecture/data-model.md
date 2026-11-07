# Target data model
Source baseline: 2026-10-09 (America/Chicago). Status: target logical design; not implemented in this repository.
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
- Route graphics depict planned fluid paths; confirmed equipment states come from action events. The selected mash tun is an insulated cooler with no mash recirculation; omit HERMS/RIMS routes.
- Temperature freshness, timers, beer age, ratings, and comparisons are derived from stored values/timestamps.
- Successful alert acknowledgement is distinct from confirming its physical action.


## Related documentation

- [Acceptance scenarios and validation rules](../requirements/acceptance-scenarios.md)
- [Current implementation status](../plan/status.md)
- [Source provenance](../references/README.md)
