# Current development status

As of November 7, 2026 (America/Chicago). This is a development snapshot, not a live production health report.

## Active repository

| Area | Observed state |
| --- | --- |
| Runtime | Root `app.py` is a Python standard-library HTTP service with `/health`; no brewing APIs |
| Tests | Four unittest tests cover health payload and repository foundation assets |
| Backend organization | `app/AGENTS.md` defines boundaries; no integrated brewing modules yet |
| Frontend | Proposed React/TypeScript structure, frontend instructions, and shared CSS tokens; no runnable frontend |
| Persistence | No active database, ORM, or migrations |
| Contracts | A versioned sensor-reading JSON schema exists; sensor adapters are not implemented |
| Delivery | Dockerfile and GitHub Actions for tests, ARM64 build/publish, and Tailscale/SSH deployment are present; Pi deployment state was not inspected in this session |
| Knowledge base | M0 documentation assembled, including source archive and screen annotations; image binaries are not stored |

## Current-instance verification

During cloud onboarding on November 7, 2026:

- Python 3.12.14 syntax checks and all four existing unittest tests passed.
- The running service returned the expected JSON from `/health` and 404 from `/`.
- Native x86_64 Docker build and HTTP health verification passed; the container ran as UID 10001 and Docker reported healthy.
- Checkout files had mode 0600, which prevented the container user from reading `app.py` in a direct build. Building from a temporary context with readable copies resolved it without changing repository source. Reusable setup/start instructions were saved in the cloud configuration draft.
- ARM64 build failed with `exec format error`. A binfmt registration attempt reported success but did not enable subsequent ARM64 builds. Native success does not validate Raspberry Pi execution.
- GitHub read access worked. No production deployment, cloud publication, or fresh-task restoration was verified.

Documentation changes do not implement brewing features. Updated check results should name the command, date, relevant commit/task when available, and the behavior actually exercised.

During knowledge-base creation on November 7, 2026, `python3 -m unittest discover -s tests -v` passed all four existing tests again. Documentation validation checked 83 local links, all nine archived source checksums, the 14 unique ordered acceptance-scenario IDs, and the presence of all three Mermaid ERD sources. `git diff --check` passed for tracked edits. These checks validate documentation consistency and the existing foundation; they do not execute the archived prototype or render the Mermaid diagrams/wireframe images.

## Supplied reference prototype

The [prototype archive](../references/README.md) describes a FastAPI/SQLite manual workflow with recipe versions, batch snapshots, timers, confirmations, manual readings, notes, review, tastings, and JSON export. It uses eight compact tables; the target logical model has 31 entities.

The supplied October 10 verification report says four backend tests and a DOM integration flow passed. These are historical reports, not tests rerun against this repository. The supplied restart-named test constructs a new client against the same application/database, rather than restarting a server process; its duplicate-confirmation test sends sequential requests rather than exercising simultaneous devices.

The prototype was not integrated or executed during knowledge-base creation. Its pinned dependencies are archived inputs, not installed application requirements or endorsed current versions. Its alerts depend on dashboard polling; closed-browser/locked-phone delivery is absent. Visual/mobile review, real Pi operation, sensors, full relational migrations, correction controls, and backup restoration remain unverified or unimplemented as described by the source.

## Next action

Begin the M1 foundation design after resolving [D-01–D-03](open-decisions.md). Use the [roadmap](roadmap.md) and [acceptance scenarios](../requirements/acceptance-scenarios.md) to scope each implementation task. Preserve `/health`, the current Docker pathway, and recorded history.
