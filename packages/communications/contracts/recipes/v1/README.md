# Recipe overview HTTP contract v1

M2/UI-04/UI-05 under [proposed ADR-0011](../../../../../docs/architecture/decisions/0011-manual-recipe-overview.md). All recipe resources are drafts; this interface does not publish, start a batch, expose the full plan, or change ingredients/steps. Generated model schemas in this directory are tested against the implemented transport models. OpenAPI is served at `/api/v1/openapi.json`.

| Method and path | Request / response |
| --- | --- |
| GET `/api/v1/recipe-drafts?limit=50&offset=0` | `draft-page.schema.json`: items plus nullable next_offset. Limit 1–100; offset 0–100000. Newest creation first, ID tie-break. Offset paging can shift during concurrent inserts; refresh after changes and deduplicate IDs while appending. |
| POST `/api/v1/recipe-drafts` | `create-draft.schema.json`: creation_id is UUID v4. First request creates an empty numbered version and returns 201 overview; repeated key returns 200 current overview without overwriting it. Simultaneous retries create one draft. |
| GET `/api/v1/recipe-drafts/{version_id}` | `overview.schema.json`; 404 if absent. Version IDs are path segments of 1–128 characters; HTTP-created IDs are UUID strings. |
| PATCH `/api/v1/recipe-drafts/{version_id}/overview` | `update-overview.schema.json`: expected_revision, name, and description are all required. Explicit null clears an optional field. Only these two text fields change; complete ingredient/step data stays intact. Returns the saved overview with edit_revision incremented once. |

Name is nullable, at most 200 Unicode characters, and nonblank when provided. Description is nullable and at most 10,000 characters. Extra fields, coerced numbers/booleans, and missing revision/text keys are rejected. Edit revisions on the wire are positive integers no larger than JavaScript's safe integer maximum. Request-body size is independently limited to 32 KiB. Browser HTML maxlength counts UTF-16 units. No implicit units, classification, targets, or publication values are inferred.

Responses use `Cache-Control: no-store`. Errors follow `error.schema.json` with code, message, and field issues. Codes/statuses: invalid_request/400, forbidden/403, not_found/404, conflict/409, request_too_large/413, unsupported_media_type/415, validation_error/422, unavailable/503. Storage failures expose no driver details or credentials. Unknown paths/methods retain the framework's ordinary routing errors.

An unsuccessful network response does not establish whether a write committed. Retain the same creation UUID until confirmation, including across a browser refresh. Save retries retain the prior expected revision; if a prior save committed, the retry gets 409 and must review current saved data. Never automatically resubmit at a newly fetched revision. Metadata updates are atomic and preserve the rest of the plan, including records not exposed by this interface.

## Local browser boundary

Recipe requests accept configured exact hostnames (default localhost/apphomebrew/apphomebrew.local) or private/loopback/Tailscale literal addresses. Extra host aliases use the config-owned BROWSER_TRUSTED_HOSTS setting. Unknown DNS hostnames are rejected to constrain rebinding. An Origin header, when present, must match scheme, host, and port; cross-site Fetch Metadata is rejected. Writes require application/json and enforce the body limit before model parsing, including streamed requests. CLI callers without browser headers remain supported on allowed hosts. No CORS permissions are added. Production and development entry pages prohibit framing.

This is a trusted local network interface, not user authentication. D-07 remains open before access is broadened. Request guards do not authorize physical brewing actions. Test requests with generated data run only against disposable test databases/containers.
