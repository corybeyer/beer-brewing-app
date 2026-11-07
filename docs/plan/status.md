# Current development status

As of November 7, 2026 (America/Chicago). This is a development snapshot, not a live production health report.

## Active repository

| Area | Observed state |
| --- | --- |
| Runtime | Root `app.py` remains the production smoke service. A separate development FastAPI factory provides `/health`, `/api/v1/readiness`, and versioned OpenAPI; no brewing APIs |
| Tests | Categorized unit/integration/contract/browser tests; repository validator regression fixtures cover placement, dependencies, visuals, metadata, secret exclusions, and source-bound pre-PR reports |
| Backend organization | FastAPI composition in `apps/api` (`brewery_api`); separate `brewery_database` and `brewery_config` packages. No brewing domain modules yet |
| Frontend | Runnable React/TypeScript/Vite preview in `apps/web`: Home/Recipes/Settings navigation, honest UI-04 preview, service readiness. Shared controls/examples in `packages/ui`, visual foundations in `packages/design-system`; recipe operations remain unavailable |
| Persistence | PostgreSQL 17 adapter/migrations in `packages/database`; role provisioning in `infrastructure/deployment/database`; credentials/configuration in `packages/config`. Root development `compose.yaml` separates administrator/migrator/runtime roles and file mounts. No business tables |
| Contracts | Versioned contracts and typed readiness client in `packages/communications`; React state stays in the web app. Backend generates v1 OpenAPI. No sensor adapters are implemented |
| Delivery | Production Dockerfile and publication/deployment workflow retained. CI now includes PostgreSQL backend tests and an ARM64 development-image build; local container execution and Pi deployment remain unverified for this change |
| Knowledge base | M0 documentation assembled, including source archive and screen annotations; four supplied wireframe image files are now available in `docs/images/` |
| Development images | `docs/images/README.md` links the four supplied wireframes to UI-01–UI-04 and documents naming, source guidance, and the cooler/no-recirculation correction; UI-05 and UI-06 images remain absent |

## Current-instance verification

During cloud onboarding on November 7, 2026:

- Python 3.12.14 syntax checks and all four existing unittest tests passed.
- The running service returned the expected JSON from `/health` and 404 from `/`.
- Native x86_64 Docker build and HTTP health verification passed; the container ran as UID 10001 and Docker reported healthy.
- Checkout files had mode 0600, which prevented the container user from reading `app.py` in a direct build. Building from a temporary context with readable copies resolved it without changing repository source. Reusable setup/start instructions were saved in the cloud configuration draft.
- ARM64 build failed with `exec format error`. A binfmt registration attempt reported success but did not enable subsequent ARM64 builds. Native success does not validate Raspberry Pi execution.
- GitHub read access worked. No production deployment, cloud publication, or fresh-task restoration was verified.

Historical documentation checks do not implement brewing features. Updated check results should name the command, date, relevant commit/task when available, and the behavior actually exercised.

During knowledge-base creation on November 7, 2026, `python3 -m unittest discover -s tests -v` passed all four existing tests again. Documentation validation checked 83 local links, all nine archived source checksums, the 14 unique ordered acceptance-scenario IDs, and the presence of all three Mermaid ERD sources. `git diff --check` passed for tracked edits. These checks validate documentation consistency and the existing foundation; they do not execute the archived prototype or render the Mermaid diagrams/wireframe images.

During the M1 PostgreSQL foundation work on November 7, 2026:

- Python 3.13.5 on native ARM64 was used locally. The four original tests passed with `python3 -m unittest discover -s tests -v`.
- All ten backend tests passed with `.venv/bin/python -m unittest discover -s tests/backend -v` and `TEST_DATABASE_URL` pointing to a temporary PostgreSQL 17.11 Unix-socket instance. Tests created/dropped a uniquely named database. They exercised HTTP contracts, invalid configuration, unavailable/missing databases, missing/unexpected schema revisions, repeatable explicit upgrades, and a populated fixture retained through baseline upgrade/downgrade/upgrade. These are not business-table or backup-restoration tests.
- `python3 -m compileall -q app.py app/brewery app/migrations tests`, `.venv/bin/python -m pip check`, development Compose configuration validation, and `git diff --check` passed. The editable backend package installed successfully.
- Docker daemon access was denied, including an attempted passwordless sudo invocation. PostgreSQL binaries were extracted under `/tmp` for the native database tests; no system PostgreSQL service was installed. Neither development-image build/runtime nor root-image regression build could be run locally. CI now defines PostgreSQL tests on Python 3.12 and ARM64 builds for both images; those new CI runs have not been observed here.
- Starlette emits a deprecation warning for its supported HTTPX test-client compatibility path; the pinned tests pass. No frontend, business API, production migration, or deployment was performed. M1 remains incomplete.

During the database-role and secret-file extension on November 7, 2026:

- [ADR-0004](../architecture/decisions/0004-database-roles-and-secrets.md) records the separate administrator/migrator/application roles and host-held credentials. Local development password files were generated in ignored `.secrets/`, never displayed or committed. The development Compose stack remains unstarted; persistent development roles will be created when its explicit provisioner runs. No production credentials, roles, or Pi configuration were changed.
- All 21 backend tests passed on Python 3.13.5 and temporary native PostgreSQL 17.11 over TCP with SCRAM authentication, using `.venv/bin/python -m unittest discover -s tests/backend -v` with a disposable `TEST_DATABASE_URL`. Four existing smoke/foundation tests also passed. The temporary instance was stopped after testing.
- New coverage verifies file-based passwords/reserved characters, invalid/conflicting credential sources, secret creation and preservation, separate authenticated roles, runtime DDL/metadata-write denial, explicit business-table grants, wrong-password rejection, idempotent provisioning, rejection of elevated existing roles, and rollback of a migration when its metadata grant fails. Role/database fixtures use unique names and are cleaned up.
- Development Compose configuration validation, dependency checks, and syntax checks passed. Docker image/runtime validation remains assigned to CI; local Docker access was not requested again. A passing native role test is not proof of container secret-mount behavior or production deployment.

## Workspace and frontend verification

During the November 7, 2026 separation-of-concerns correction:

- [ADR-0005](../architecture/decisions/0005-workspace-boundaries.md) adopts the brewer's `apps/`, concern-specific `packages/`, `infrastructure/`, `scripts/`, and categorized tests layout. ADRs, network/data-flow documentation, and brewery equipment/drawing/build-plan ownership were relocated/documented. [The ownership map](../development/repository-layout.md) records allowed dependencies. Packages without implemented capabilities contain ownership guidance rather than speculative runtime code.
- Node 24.22.2 was downloaded to a temporary local tool directory and verified against Node's published SHA-256 checksum. Root npm workspaces use one lock; source packages are imported through named exports. Python editable installation succeeded with distinct API/database/config source mappings.
- `npm run build` passed (strict TypeScript plus Vite). `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm test` passed all 33 browser checks across desktop/tablet/phone on the relocated workspace, including axe A/AA checks, navigation/history, loading/disabled/invalid/shared-component states, timeouts/network failures, retries, and cancellation of superseded requests. Ready-service browser screenshots use simulated responses, not live recipe/database data. Desktop and phone screenshots were visually inspected.
- All 29 Python tests passed using `.venv/bin/python -m unittest discover -s tests -v` with a disposable native PostgreSQL 17.11 TCP/SCRAM `TEST_DATABASE_URL`. This includes the original service/contract checks, moved migration/role tests, and four dependency/style boundary guards. The temporary test instance was stopped.
- After restricting Vite's file-serving roots, the affected recipe/gallery checks passed on all three viewports, and three additional browser checks confirmed that synthetic private files, environment files, and backend source are refused. No actual password file was read by those checks. A real FastAPI process and Vite proxy were started temporarily: readiness returned HTTP 503 for an intentionally unavailable database, and the page displayed the unavailable state. Both temporary services were stopped. The component gallery was also checked absent from the production bundle.
- A fresh root `npm ci`, production build, Python syntax/dependency checks, development Compose configuration validation, active documentation file links, and whitespace checks passed. Boundary checks were rerun after expanding their source coverage. New assets/dependencies and `.secrets/` remain outside Git unless explicitly source-owned; no generated credentials are present in publishable source.
- PR #4 previously passed GitHub CI and merged. Its success covers the earlier backend foundation; CI has not yet run against these relocated paths or the frontend job. New runtime container builds, secret mounts, and production serving remain unverified. The production `app.py`, root Dockerfile, and publication/deployment workflow are unchanged. No production database or deployment was performed.

## Repository validation tooling

On November 7, 2026, [ADR-0006](../architecture/decisions/0006-pre-pr-validation.md) adds the required local `python3 scripts/pre_pr.py` command and independent `Repository policy` CI job. The [documented policy](../development/pre-pr-validation.md) checks Git-visible source ownership, Python/TypeScript imports, package exports/declarations/cycles, library-driven presentation, centralized tokens, migration graph/readiness consistency, sensitive/generated files, and active documentation links. Exceptions are exact, justified, and ADR-backed; secret and parser failures cannot be waived.

The current repository passed the fast checker. Positive/negative regression fixtures passed (11 Python policy tests, eight frontend parser tests, and three pre-PR report tests). Full pre-PR step outcomes and missing database coverage are recorded by the command in ignored `.validation/pre-pr.json`; stale source/base commits invalidate that report. CI and actual branch protection remain distinct: the job is defined in source, but no GitHub ruleset or production configuration was changed.

PR #5's first frontend CI build exposed an ARM64-generated npm lock missing TypeScript's optional Linux x64 compiler package. The lock was regenerated from a clean manifest-only workspace without changing declared dependency versions. The policy validator now rejects missing/mismatched optional-dependency lock records, with a regression fixture for a compiler installed across ARM64/x64 and hoisted package resolution. CI must verify the corrected Linux x64 build independently of local ARM64 tests.

## Supplied reference prototype

The [prototype archive](../references/README.md) describes a FastAPI/SQLite manual workflow with recipe versions, batch snapshots, timers, confirmations, manual readings, notes, review, tastings, and JSON export. It uses eight compact tables; the target logical model has 31 entities.

The supplied October 10 verification report says four backend tests and a DOM integration flow passed. These are historical reports, not tests rerun against this repository. The supplied restart-named test constructs a new client against the same application/database, rather than restarting a server process; its duplicate-confirmation test sends sequential requests rather than exercising simultaneous devices.

The prototype was not integrated or executed during knowledge-base creation. Its pinned dependencies are archived inputs, not installed application requirements or endorsed current versions. Its alerts depend on dashboard polling; closed-browser/locked-phone delivery is absent. Visual/mobile review, real Pi operation, sensors, full relational migrations, correction controls, and backup restoration remain unverified or unimplemented as described by the source.

## Next action

Review the workspace/frontend change and run CI on its new paths. Complete M1 by validating development containers and production-serving/deployment compatibility. D-02 is settled by ADR-0002/ADR-0005; feature data contracts in D-03 remain open. Use the [roadmap](roadmap.md) and [acceptance scenarios](../requirements/acceptance-scenarios.md) to scope each task. Preserve `/health`, the current Docker pathway, and recorded history.
