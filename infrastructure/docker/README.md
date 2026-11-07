# Docker

`api.Dockerfile` builds the separate development backend. Root `Dockerfile` remains the production smoke image until a controlled replacement. Root `compose.yaml` is development-only and uses per-service secret files. CI validates both ARM64 image builds.

## M1 runtime validation

Run `python3 scripts/development/check_containers.py` from the repository root with Docker daemon access and Compose v2. The `Container runtime` CI job runs the same check on native Linux x64; the existing ARM64 job separately builds both images.

The check builds the real development image, provisions fresh PostgreSQL roles, runs migrations, and waits for Docker health and HTTP readiness. It verifies that the non-root API receives only its read-only application secret and the database has no published port. It stops PostgreSQL to check that `/health` stays live while readiness returns sanitized HTTP 503, then verifies recovery. It removes/recreates containers and checks the PostgreSQL system identifier and migrated readiness against the retained volume. Finally, it builds/runs the retained root smoke image and checks its non-root user, HTTP payload, and Docker health.

Each run uses a unique Compose project, explicitly isolated network/volume, temporary generated passwords, and random loopback HTTP ports. Cleanup removes only that run's containers, test volume, network, and smoke image; development database volumes and saved `.secrets/` files are not used. Interrupted runs that bypass cleanup may leave resources prefixed `brewery-check-`; inspect them before removing anything manually.

These checks do not cover UI-to-container traffic, production frontend serving, Pi runtime, production deployment/rollback, or backup restoration (AC-14). No brewing acceptance scenario is completed. Production replacement remains a separate controlled change; see [production ownership](../deployment/production/README.md).

## UI/API candidate

The separate `candidate.Dockerfile` builds the existing frontend with Node and copies only its production build into a non-root Python image. It serves UI assets and `/api/v1` on port 8080, with `/health` unchanged. Node, the component gallery, source maps, provisioning commands, and credentials are not part of the served application. The root production image and publish/deploy workflow remain unchanged. The topology is [proposed ADR-0007](../../docs/architecture/decisions/0007-production-serving-candidate.md), pending explicit adoption and a controlled Pi trial.

To check the real candidate container, install Node 24, run `npm ci`, install Playwright Chromium, then run:

```sh
python3 scripts/development/check_containers.py --candidate
```

This substitutes only the isolated stack's API image/port. Provisioning and migration continue through the existing operator image. Desktop/tablet/phone browsers use the real built UI and PostgreSQL-backed API on the same origin during startup, database outage, and recovery (18 browser checks). No responses are mocked. Checks also retain the existing secret/private-network, persistence, and smoke-image regression coverage. Results live under ignored `tests/e2e/test-results/serving-*`; `Candidate UI and API runtime` CI uploads them. The ARM64 build job separately builds all three images without publication.

For host-only testing, build with `npm run build`, configure the existing host [database setup](../../docs/architecture/backend-foundation.md), and run the FastAPI factory with `WEB_ASSETS_DIRECTORY` set to the absolute `apps/web/dist` path. Omitting the variable preserves API-only mode; an empty, relative, missing, or incomplete directory fails composition. The server exposes only the entry HTML and `/assets`, rejects unknown API/private/source paths, and revalidates the entry HTML on reload. Hash navigation works without an HTML fallback for arbitrary paths.

Live serving tests can target that temporary host server with `BREWERY_SERVING_BASE_URL`, `BREWERY_SERVING_READINESS=ready` (or `unavailable`), and optional `BREWERY_SERVING_PHASE`, using `npm exec -- playwright test --config apps/web/playwright.serving.config.ts`. They are separate from the default Vite/browser suite and source-bound pre-PR report, because the serving checks require a running candidate server. Native host success does not establish container or Pi runtime behavior.
