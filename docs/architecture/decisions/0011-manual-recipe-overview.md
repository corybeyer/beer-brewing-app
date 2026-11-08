# ADR-0011: Manual recipe overview API and editor

Status: Proposed — November 7, 2026

## Context

M2 has deployed draft storage but no browser write flow. UI-04/UI-05 need a narrow manual overview editor without settling publication, ingredient editing, classification, or brewing targets. The local HTTP service currently has no authentication; new writes need browser-origin and host protections without changing deployment topology.

## Proposed decision

Expose a v1 draft collection with bounded offset pagination, idempotent empty-draft creation keyed by a client-generated UUID v4, metadata reads, and overview-only PATCH with a required positive edit revision. A repeated creation key returns the same current draft without overwriting it. Only name (nullable, maximum 200 characters) and description (nullable, maximum 10,000 characters) can be edited. Preserve the entire ingredient/step plan. Domain services own use-case coordination; storage exceptions cross the port as sanitized RecipeStorageUnavailable errors; the database implements the existing port plus summary listing. No migration is needed.

Use strict versioned JSON schemas, reject extra fields, sanitize storage failures, and return stable field issues, 404, 409, and 503 semantics. Recipe responses are no-store. Bound write bodies to 32 KiB before model parsing. Require application/json, reject cross-site Fetch Metadata and foreign Origin headers, and allow only the configured local hostname set or private/loopback/Tailscale literal addresses as recipe request hosts. CLI requests without browser headers remain supported on allowed hosts. Entry pages prohibit framing. Exact configured aliases are read through the config package. These are browser request protections, not user authentication; D-07 remains open before expanding access.

The React library creates/open drafts and edits overview text using shared form controls. Failed saves and conflicts retain typed values. Conflicts require explicit review of the latest saved version before retry; no automatic overwrite. Unsaved text remains in memory while navigating between app pages; browser reload/close warns before discarding it. Switching drafts or creating another requires a keep/discard choice. Creation keys use getRandomValues-compatible UUID generation so plain HTTP on the Pi works without assuming crypto.randomUUID is available. Loading/errors do not masquerade as an empty database. Unsupported publication/import/style/ingredient/step controls stay unavailable.

## Verification and limits

Use real PostgreSQL API tests for idempotency, metadata preservation, stale edits, unavailable databases, ownership constraints, and request guards. Validate generated schemas against model definitions. Browser tests cover phone/tablet/desktop, accessibility, failures/timeouts, conflict recovery, dirty navigation, and the insecure-context UUID fallback. Extend real serving tests to exercise creation, save, reload, and database outage/recovery against disposable containers; never create synthetic records in production. Existing health, schema, deployment, and rollback contracts stay intact. AC-01–AC-03 and full UI-04/UI-05 remain incomplete beyond this slice.

## Reference

[OWASP CSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) informs the JSON/origin/Fetch Metadata boundary. Default trusted hostnames are localhost, apphomebrew, and apphomebrew.local; extra exact names use BROWSER_TRUSTED_HOSTS. Private IP handling does not authorize public exposure.
