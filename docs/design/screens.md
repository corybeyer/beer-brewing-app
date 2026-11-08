# Screen specifications

Status: target behavior derived from the supplied wireframes and project reference. Screen IDs remain stable so tasks and PRs can cite them. These specifications do not indicate implemented UI. Use [shared design principles](design-principles.md) and the [wireframe annotations](wireframes/README.md).

## Screen map

| ID | Screen | User goal | Relevant acceptance scenarios |
| --- | --- | --- | --- |
| UI-01 | Brew-day dashboard | Understand the current action, readings, timers, and next reminders | AC-05–AC-10 |
| UI-02 | Recipe steps | Define every step, dependency, timing anchor, and ingredient addition | AC-01, AC-02, AC-05 |
| UI-03 | Batch review and tastings | Review actual results, record tastings, and create a historical recipe revision | AC-03, AC-10–AC-12 |
| UI-04 | Recipe library and ingredients | Find recipes, manage versions and ingredients, review imports and attribution | AC-01, AC-03, AC-13 |
| UI-05 | Recipe overview and style | Describe and classify a recipe and review its brewing targets | AC-03, AC-13 |
| UI-06 | Batch setup | Review the plan, equipment, readiness, substitutions, and input sources | AC-04, AC-09, AC-11 |

The scenario details are in [acceptance scenarios](../requirements/acceptance-scenarios.md). UI-specific checks below supplement them.

## UI-01: Brew-day dashboard

- Show batch identity, recipe version, target volume, stage progression, and all ordered steps.
- Give current instructions, elapsed/remaining times, and upcoming reminders visual priority. A hold may run alongside multiple scheduled additions.
- Show HLT, mash tun, and kettle targets/readings with units, source, measurement age, and quality. Missing values use an explicit no-reading state; charts do not invent continuous manual data.
- Provide quick measurement entry, notes, action confirmation, and access to the full step list/log.
- Distinguish planned fluid paths, brewer-confirmed equipment state, and measured telemetry. Do not present the graphic as a hardware control.
- A timer ending creates a reminder; advancing requires the defined brewer confirmation.

Checks: refresh during a hold without resetting time; recover after service restart; display stale/missing data clearly; show parallel reminders; prevent a double confirmation from two devices.

## UI-02: Recipe steps

- Use Overview, Ingredients, and Steps navigation within a version. Show draft/publication state and source.
- Include every step on mobile and desktop. Support editing order without breaking dependency references; provide a keyboard alternative to drag operations.
- Define action type, instructions, vessel/equipment role, target, duration, dependency, timing anchor, offset, ingredient portion, and confirmation requirement as applicable.
- Explain timing clearly: 45 minutes after confirmed start is 15 minutes remaining in a 60-minute boil. Recalculate/review the schedule explicitly if duration changes.
- Allow incomplete draft work while blocking invalid publication or batch start with actionable errors. The mockup's Start batch button on a draft is not permission to bypass readiness validation.

Checks: reject cycles and cross-version links without partial saves; keep references valid after reordering; show all steps at narrow widths; preserve a published version when editing through a new draft.

## UI-03: Batch review and tastings

- Offer Overview, Brew log, and Tastings views. Compare matching planned/actual gravity and volume purposes; absent actuals stay absent.
- Show recipe version, brew/packaging dates when known, notes, deviations, and the complete action history.
- Maintain a tasting timeline with appearance, aroma, flavor, mouthfeel, off-flavors, optional 1–5 rating, overall notes, would-brew-again choice, and ideas for the next batch.
- Derive beer age from the saved packaging date; do not fabricate an age if it is unknown. Label the summary rating as the latest tasting rather than an unexplained average.
- Create a draft revision linked to selected batch/tasting feedback. Suggestions require review; preserve the original records. Corrections retain history.
- Batch comparison is a later capability; do not show it as available until implemented and validated.

Checks: multiple tastings retain chronology; invalid ratings are rejected; creating a revision preserves batch snapshots and provenance; mobile keeps history and selected-tasting detail accessible.

## UI-04: Recipe library and ingredient entry

- Search by recipe name and filter by style; show version, readiness, volume, and source.
- Provide manual recipe creation and ingredient groups for grain, hops, yeast, and other additions, including quantity, unit, specifications, and intended use.
- Link scheduled portions to brewing steps rather than duplicating ingredient amounts in free text.
- Preserve personal, book, and website attribution separately from style. Imported text/file/URL workflows produce reviewable drafts with missing fields visible.
- Upload, URL parsing, OCR, and AI extraction are proposed capabilities; only expose operational controls for supported modes.

Checks: edits preserve draft data; invalid quantities/units get field-specific feedback; scheduled portions do not double-count ingredients; incomplete imports cannot silently become ready.

## UI-05: Recipe overview and style

Described in the reference; its image was not supplied in the current image set. Show name, description, tags, source, target volumes/gravities, and BJCP selection with guideline edition and code. Support Unclassified / Custom and treat style ranges as references. Keep style and source independent.

Checks: a custom recipe can be saved; classification is preserved in version/batch history; missing required publication fields have clear feedback.

## UI-06: Batch setup

Described in the reference; its image was not supplied in the current image set. Review recipe version, equipment, planned date/name/volume, readiness checklist, substitutions, and manual/sensor input choices. Create recipe/equipment snapshots together. Resolve equipment routes and validate required preparation before execution.

Checks: later profile or recipe edits leave the batch intact; substitutions retain original versus actual ingredient data; manual-only setup works without sensor credentials; entering the session does not claim that heating or a transfer occurred.

## Shared interaction and responsive checks

Use semantic tokens and shared accessible components. Preserve primary tasks across desktop/tablet/phone layouts; do not require pixel-for-pixel copies. Include visible focus, keyboard operation, generous touch targets, and statuses communicated beyond color.

Specify empty, loading, validation-error, request-failure, disconnected, disabled, and success states for each implemented flow. Preserve entered data on recoverable errors. Validate real browser rendering and narrow viewports; DOM tests alone do not establish visual quality.


## Implemented manual overview slice (M2)

UI-04/UI-05 now have a local implementation for listing saved drafts, idempotent empty-draft creation, and editing a version's name/description through the [v1 overview API](../../packages/communications/contracts/recipes/v1/README.md). Loading/failure states are distinct from an empty database. Fields preserve entered values after errors. On conflict, review current saved data and explicitly choose whether to keep entered values or load saved values before retrying; no automatic overwrite occurs.

Unsaved text persists while navigating Home/Settings/Recipes within the running page. Reload/close warns; switching drafts/new creation offers a keep/discard choice. A pending creation UUID is kept in session storage so a lost creation reply can be retried without duplication. The editor's unsupported search/style/ingredient/step/target/import/publication capabilities remain clearly unavailable. This is partial UI-04/UI-05 support and does not complete AC-01–AC-03 or the full screens.
