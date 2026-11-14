# Recipe and conversion HTTP contract v1

M2/UI-02/UI-04/UI-05 under [proposed ADR-0011](../../../../../docs/architecture/decisions/0011-manual-recipe-overview.md). All recipe resources are drafts; this interface does not publish, start a batch, or expose a combined full-plan resource. Generated model schemas in this directory are tested against the implemented transport models. OpenAPI is served at `/api/v1/openapi.json`.

| Method and path | Request / response |
| --- | --- |
| GET `/api/v1/recipe-drafts?limit=50&offset=0` | `draft-page.schema.json`: items plus nullable next_offset. Limit 1–100; offset 0–100000. Newest creation first, ID tie-break. Offset paging can shift during concurrent inserts; refresh after changes and deduplicate IDs while appending. |
| POST `/api/v1/recipe-drafts` | `create-draft.schema.json`: creation_id is UUID v4. First request creates an empty numbered version and returns 201 overview; repeated key returns 200 current overview without overwriting it. Simultaneous retries create one draft. |
| GET `/api/v1/recipe-drafts/{version_id}` | `overview.schema.json`; 404 if absent. Version IDs are path segments of 1–128 characters; HTTP-created IDs are UUID strings. |
| PATCH `/api/v1/recipe-drafts/{version_id}/overview` | `update-overview.schema.json`: expected_revision, name, and description are all required. Explicit null clears an optional field. Only these two text fields change; complete ingredient/step data stays intact. Returns the saved overview with edit_revision incremented once. |
| GET `/api/v1/recipe-drafts/{version_id}/steps` | `steps.schema.json`: coherent version ID, edit revision, and ordered steps. |
| PATCH `/api/v1/recipe-drafts/{version_id}/steps` | `update-steps.schema.json`: expected_revision and complete replacement step list. |

Name is nullable, at most 200 Unicode characters, and nonblank when provided. Description is nullable and at most 10,000 characters. Extra fields, coerced numbers/booleans, and missing revision/text keys are rejected. Edit revisions on the wire are positive integers no larger than JavaScript's safe integer maximum. Request-body size is independently limited to 32 KiB. Browser HTML maxlength counts UTF-16 units. No implicit units, classification, targets, or publication values are inferred.

Responses use `Cache-Control: no-store`. Errors follow `error.schema.json` with code, message, and field issues. Codes/statuses: invalid_request/400, forbidden/403, not_found/404, conflict/409, request_too_large/413, unsupported_media_type/415, validation_error/422, unavailable/503. Storage failures expose no driver details or credentials. Unknown paths/methods retain the framework's ordinary routing errors.

An unsuccessful network response does not establish whether a write committed. Retain the same creation UUID until confirmation, including across a browser refresh. Save retries retain the prior expected revision; if a prior save committed, the retry gets 409 and must review current saved data. Never automatically resubmit at a newly fetched revision. Metadata updates are atomic and preserve the rest of the plan, including records not exposed by this interface.

## Local browser boundary

Recipe requests accept configured exact hostnames (default localhost/apphomebrew/apphomebrew.local) or private/loopback/Tailscale literal addresses. Extra host aliases use the config-owned BROWSER_TRUSTED_HOSTS setting. Unknown DNS hostnames are rejected to constrain rebinding. An Origin header, when present, must match scheme, host, and port; cross-site Fetch Metadata is rejected. Writes require application/json and enforce the body limit before model parsing, including streamed requests. CLI callers without browser headers remain supported on allowed hosts. No CORS permissions are added. Production and development entry pages prohibit framing.

This is a trusted local network interface, not user authentication. D-07 remains open before access is broadened. Request guards do not authorize physical brewing actions. Test requests with generated data run only against disposable test databases/containers.

## Ingredient editing

GET `/api/v1/recipe-drafts/{version_id}/ingredients` returns `ingredients.schema.json`: a coherent version ID, edit revision, and ordered ingredient list. PATCH at the same path accepts `update-ingredients.schema.json`, containing the required expected_revision and complete replacement ingredient list. Overview endpoints retain their existing contracts. All origin/host/media guards, no-store headers, and error semantics above also apply. Ingredient writes have a separate 512 KiB body cap; creation/overview writes retain their 32 KiB cap.

Each row has a stable id plus required nullable name, category, quantity, and unit keys. New writes allow up to 100 rows, IDs up to 128 characters, and names up to 200 characters. Quantity is a decimal **string**, never a JSON number: up to 12 integer and 12 fractional digits, no sign/exponent/grouping, positive when present. Blank browser fields become null. Reads preserve existing storage values without imposing these new write limits or truncating rows. The 512 KiB ingredient cap accommodates compact JSON for all 100 rows at their field limits, including fully escaped supplementary Unicode names/IDs. Declared and streamed requests exceeding it fail before parsing or saving.

Categories and units follow the [draft catalogue](../../../../../docs/requirements/recipe-plan-validation.md). No automatic conversions occur. The selected path supplies version ownership; extra per-row version_id fields are rejected. IDs need only be unique within a version. Keep IDs when editing so existing addition references remain valid. Removing a referenced ingredient, reducing an amount below allocated portions, or changing to a mismatched addition unit fails with field-specific issues and saves nothing. Metadata, steps, dependencies, and additions remain intact.

The edit revision is shared with overview and all future plan writes. A stale overview or ingredient save returns 409, even when the other writer edited a different section. The UI retains rows on failure and requires explicit review of the latest saved ingredients before retrying a conflict. An ingredient save cannot silently advance a stale overview's revision; only a save from the exact current overview revision can advance its revision locally.

## Grain conversion preview and Apply

The same interface supports the one-to-one C1 conversion slice described in [extract conversion](../../../../../docs/plan/extract-conversion.md) and [proposal snapshots](../../../../../docs/requirements/conversion-proposal-snapshots.md). All endpoints inherit the local host/origin boundary, `no-store` responses, 32 KiB body cap, and error codes above.

| Method and path | Request / response |
| --- | --- |
| GET `/api/v1/recipe-drafts/catalogue/grains` | Ordered list of immutable grain revisions with source label/date, potential status, and flavor notes. An empty list means no profiles are available. |
| POST `/api/v1/recipe-drafts/{version_id}/conversion-proposals` | `create-conversion.schema.json`; expected_revision plus source/target IDs and explicit potential/recovery/provenance/comparison point. Stores an immutable preview and returns `conversion-preview.schema.json` with exact rational result and rounded display amount. |
| GET `/api/v1/recipe-drafts/{version_id}/conversion-proposals/{proposal_id}` | Reloads a retained preview after an uncertain browser request; the proposal must belong to this version. |
| POST `/api/v1/recipe-drafts/{version_id}/conversion-proposals/{proposal_id}/apply` | `apply-conversion.schema.json`; rechecks the original revision and atomically replaces the complete validated plan. Returns the incremented overview. A second or stale Apply returns 409. |

The target mass display is rounded to 0.001 of the chosen unit; the exact rational amount remains in the retained proposal. The response asks the brewer to verify scale precision. Apply is a distinct user action. This estimates equal gravity contribution at the selected comparison point; it does not establish equal flavor, mash feasibility, or recipe readiness. Blend proposals and mash-step adaptation are outside this snapshot format.
The edit revision is shared by overview, ingredient, step, and future plan writes. A stale save returns 409, even when the other writer edited a different section. The UI retains values on failure and requires explicit review of the latest saved section before retrying a conflict. An ingredient or step save cannot silently advance a stale overview's revision; only a save from the exact current overview revision can advance it locally.

## Manual step editing

GET `/api/v1/recipe-drafts/{version_id}/steps` reads the complete ordered list and the IDs of steps that own ingredient additions; PATCH at the same path replaces the step list with an expected_revision. The shared revision covers overview, ingredients, and steps, so stale writes return 409.

Each step has a stable ID, nullable title/instructions, dependency IDs, and a nullable timing anchor. Writes accept at most 100 steps; titles are limited to 200 characters, instructions to 2,000, and each dependency list to 100 IDs. The step request cap is 2 MiB. The selected path owns version identity. The complete proposed step list is validated against itself and the unchanged ingredient/addition records; missing references, cycles, and removal of a step used by an addition fail without saving. The UI disables removal while a step has dependent links or ingredient additions. Reordering changes display positions only, so step IDs and links stay stable. The browser offers keyboard move-up/move-down controls, editable links, retained values on errors, and explicit conflict review. Duration, offset, action type, vessel role, targets, confirmation rules, publication, and batch timers remain future work.
