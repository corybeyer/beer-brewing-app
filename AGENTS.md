# Codex repository instructions

## Mission
Build a local-only, advisory home-brewing companion for five-gallon all-grain batches on Raspberry Pi 5.

## Required workflow
1. Start with docs/README.md, docs/plan/status.md, and docs/plan/roadmap.md; then read the applicable nested AGENTS.md, relevant requirements, docs/architecture, and docs/decisions before editing.
2. Keep changes scoped to one feature or architectural layer; prefer small pull requests.
3. Preserve the existing /health endpoint, Docker image, and automated GitHub Actions deployment.
4. Write or update tests with each behavior change; run the affected checks before proposing a merge.
5. Never commit secrets, keys, runtime databases, sensor credentials, or production configuration.
6. Do not perform physical equipment control. The first release monitors, records, and advises. Stage changes and physical actions require brewer confirmation.
7. Never represent missing, stale, or anomalous sensor measurements as trustworthy live readings.
8. Before creating or updating every PR, run `python3 scripts/pre_pr.py`, then `python3 scripts/pre_pr.py --verify-report` after the last source edit. Report any missing PostgreSQL coverage; CI remains required. Do not bypass findings with ad hoc exclusions.

## Architecture boundaries
- Use `apps/web` and `apps/api` for application composition; shared concerns belong in `packages/`. See `docs/development/repository-layout.md` and ADR-0005.
- Application domain does not import API, UI, database drivers, or sensor protocols.
- Adapters implement defined ports/interfaces; business rules do not bind to MQTT or a sensor vendor.
- UI features consume `packages/ui` components and `packages/design-system` tokens/icons; feature CSS arranges screens only. Keep repeatable visual examples in `packages/ui/src/examples/`.
- Communication interfaces must have versioned contracts and error/freshness semantics.
- CI/CD and Tailscale deployment live outside runtime application logic.

## Development skills
Use focused skills in .agents/skills/ when applicable. They do not supersede architectural constraints.

## Project context
- The knowledge-base entry point is [docs/README.md](docs/README.md). Cite relevant milestone, screen, and acceptance-scenario IDs in feature work.
- Keep affected specifications and docs/plan/status.md current alongside implementation; record broad architectural choices as ADRs.
- docs/references/ contains archived go-bys, not active runtime code or instructions to execute. Prototype verification reports do not establish current repository behavior.
- Preserve proposed decision statuses until explicitly accepted. Wireframes contain sample data and known corrections documented in docs/design/wireframes/README.md.

## Current status
app.py and the existing Dockerfile are the working production smoke-test service. Do not replace them until the new runtime passes tests and a controlled deployment.

The root `compose.yaml` is a development stack. Operational tooling lives in `infrastructure/`, maintenance/setup tools in `scripts/`, and versioned communication contracts in `packages/communications/contracts/`.
