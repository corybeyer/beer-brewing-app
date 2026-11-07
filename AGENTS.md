# Codex repository instructions

## Mission
Build a local-only, advisory home-brewing companion for five-gallon all-grain batches on Raspberry Pi 5.

## Required workflow
1. Read the applicable nested AGENTS.md, relevant docs/architecture, and docs/decisions before editing.
2. Keep changes scoped to one feature or architectural layer; prefer small pull requests.
3. Preserve the existing /health endpoint, Docker image, and automated GitHub Actions deployment.
4. Write or update tests with each behavior change; run the affected checks before proposing a merge.
5. Never commit secrets, keys, runtime databases, sensor credentials, or production configuration.
6. Do not perform physical equipment control. The first release monitors, records, and advises. Stage changes and physical actions require brewer confirmation.
7. Never represent missing, stale, or anomalous sensor measurements as trustworthy live readings.

## Architecture boundaries
- Application domain does not import API, UI, database drivers, or sensor protocols.
- Adapters implement defined ports/interfaces; business rules do not bind to MQTT or a sensor vendor.
- UI features consume shared design-system components and semantic tokens; avoid arbitrary colors and inline styles.
- Communication interfaces must have versioned contracts and error/freshness semantics.
- CI/CD and Tailscale deployment live outside runtime application logic.

## Development skills
Use focused skills in .agents/skills/ when applicable. They do not supersede architectural constraints.

## Current status
app.py and the existing Dockerfile are the working production smoke-test service. Do not replace them until the new runtime passes tests and a controlled deployment.
