# ADR-0007: Single-origin production serving candidate

Status: Proposed — November 7, 2026

## Context

M1 has a tested React preview and separate FastAPI/PostgreSQL foundation, but the production image only serves `/health`. The brewer requested beginning production frontend/API integration after PR #6. This candidate must be independently testable without replacing the working smoke service or modifying Pi-owned configuration.

## Proposed decision

Build the existing web application in a Node stage and copy only its production output into a separate Python runtime image. FastAPI composition optionally serves `/`, `/index.html`, and `/assets` from an explicitly configured build directory. Existing hash navigation requires no fallback of unknown API paths to HTML. Use one origin on port 8080 for both browser assets and `/api/v1`; keep credentials and database connections on the server. Development API-only mode remains available on port 8081.

Environment parsing belongs to `packages/config`; static HTTP composition belongs to `apps/api`; Docker composition/testing belongs to infrastructure and scripts. Missing or incomplete configured assets must fail startup with a sanitized error. Serve the entry HTML with revalidation so image replacement cannot leave a cached entry document pointing at removed assets.

The candidate image contains no Node runtime, frontend development server, source maps, component gallery, or provisioning commands. Database provisioning/migration continues as an explicit operation using the existing operator image. Liveness retains `/health`; Docker readiness requires the expected database schema. No business schema or brewing action changes.

## Alternatives

A reverse proxy/static server in another container would also support same-origin routing, but adds another service and routing configuration for this small local application. Publishing separate browser/API origins would add CORS and client endpoint configuration. Replacing the root Dockerfile immediately would deploy an application requiring unprovisioned production database configuration and is excluded from this candidate.

## Validation and adoption

Build both candidate architectures in CI. Exercise the candidate against the real disposable PostgreSQL stack and check desktop/tablet/phone browser readiness, database outage, recovery, and denied private/source paths through the production serving path. Retain the root smoke-image regression check.

This proposed record does not authorize automatic replacement of the Pi runtime. Before adoption, explicitly accept the topology, review Pi-owned configuration and access restrictions, provision credentials/storage, verify backup/restore and migration/rollback procedures, and perform a controlled ARM64 rollout. Keep root `app.py`, Dockerfile, and publish/deploy workflow unchanged for this task. This supports M1/UI-04; no brewing acceptance scenario, including AC-14 restoration, is completed.
