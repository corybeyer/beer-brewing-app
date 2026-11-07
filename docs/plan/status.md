# Current development status

As of November 7, 2026 (America/Chicago). This is a development snapshot, not a live production health report.

## Active repository

| Area | Observed state |
| --- | --- |
| Runtime | Root `app.py` remains the production smoke service. A separate development FastAPI factory provides `/health`, `/api/v1/readiness`, and versioned OpenAPI; no brewing APIs |
| Tests | Four original unittest tests plus backend configuration/API and real PostgreSQL migration tests under `tests/backend/` |
| Backend organization | Installable `brewery` package under `app/brewery/`; no brewing domain modules yet |
| Frontend | Proposed React/TypeScript structure, frontend instructions, and shared CSS tokens; no runnable frontend |
| Persistence | PostgreSQL 17, SQLAlchemy/Psycopg adapter, and Alembic baseline; no business tables. Development Compose separates administrator, schema-owning migrator, and restricted runtime roles; passwords come from per-service file mounts |
| Contracts | Development backend generates version 1 OpenAPI with explicit readiness failure semantics. Existing versioned sensor-reading schema remains unimplemented by sensor adapters |
| Delivery | Production Dockerfile and publication/deployment workflow retained. CI now includes PostgreSQL backend tests and an ARM64 development-image build; local container execution and Pi deployment remain unverified for this change |
| Knowledge base | M0 documentation assembled, including source archive and screen annotations; image binaries are not stored |

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

- [ADR-0004](../decisions/0004-database-roles-and-secrets.md) records the separate administrator/migrator/application roles and host-held credentials. Local development password files were generated in ignored `.secrets/`, never displayed or committed. The development Compose stack remains unstarted; persistent development roles will be created when its explicit provisioner runs. No production credentials, roles, or Pi configuration were changed.
- All 21 backend tests passed on Python 3.13.5 and temporary native PostgreSQL 17.11 over TCP with SCRAM authentication, using `.venv/bin/python -m unittest discover -s tests/backend -v` with a disposable `TEST_DATABASE_URL`. Four existing smoke/foundation tests also passed. The temporary instance was stopped after testing.
- New coverage verifies file-based passwords/reserved characters, invalid/conflicting credential sources, secret creation and preservation, separate authenticated roles, runtime DDL/metadata-write denial, explicit business-table grants, wrong-password rejection, idempotent provisioning, rejection of elevated existing roles, and rollback of a migration when its metadata grant fails. Role/database fixtures use unique names and are cleaned up.
- Development Compose configuration validation, dependency checks, and syntax checks passed. Docker image/runtime validation remains assigned to CI; local Docker access was not requested again. A passing native role test is not proof of container secret-mount behavior or production deployment.

## Supplied reference prototype

The [prototype archive](../references/README.md) describes a FastAPI/SQLite manual workflow with recipe versions, batch snapshots, timers, confirmations, manual readings, notes, review, tastings, and JSON export. It uses eight compact tables; the target logical model has 31 entities.

The supplied October 10 verification report says four backend tests and a DOM integration flow passed. These are historical reports, not tests rerun against this repository. The supplied restart-named test constructs a new client against the same application/database, rather than restarting a server process; its duplicate-confirmation test sends sequential requests rather than exercising simultaneous devices.

The prototype was not integrated or executed during knowledge-base creation. Its pinned dependencies are archived inputs, not installed application requirements or endorsed current versions. Its alerts depend on dashboard polling; closed-browser/locked-phone delivery is absent. Visual/mobile review, real Pi operation, sensors, full relational migrations, correction controls, and backup restoration remain unverified or unimplemented as described by the source.

## Next action

Complete M1 by settling frontend tooling (D-02), adding the UI foundation, and validating development containers and controlled deployment compatibility. [ADR-0003](../decisions/0003-postgresql-foundation.md) settles backend entrypoint and persistence tooling; feature data contracts in D-03 remain open. Use the [roadmap](roadmap.md) and [acceptance scenarios](../requirements/acceptance-scenarios.md) to scope each task. Preserve `/health`, the current Docker pathway, and recorded history.
