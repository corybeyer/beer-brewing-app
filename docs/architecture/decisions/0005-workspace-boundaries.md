# ADR-0005: Workspace packages separated by responsibility

Status: Accepted — November 7, 2026

## Context

The brewer clarified the intended `apps/`, `packages/`, `infrastructure/`, and categorized `tests/` layout. This replaces the earlier app/web/infra organization. The purpose is enforced separation of concerns, including repeatable visual rules and shared components outside screen code.

## Decision

- `apps/web` owns browser composition, navigation, and feature layouts. `apps/api` owns FastAPI composition and HTTP handling.
- `packages/ui` owns reusable React controls and repeatable visual examples. `packages/design-system` owns semantic tokens, fonts, icons, and global foundations. UI depends on the design system; the design system never imports UI or application features.
- `packages/database` owns the PostgreSQL adapter and Alembic migrations. `packages/config` owns environment/credential parsing. Python packages have distinct names and explicit setuptools source mappings; API/domain code cannot accidentally import deployment helpers.
- `packages/communications` owns versioned transport contracts and the browser readiness adapter. Keep React hooks in the web application. Domain, integrations, and validation have dedicated ownership directories; unimplemented capabilities are documented rather than filled with speculative code.
- Use npm workspaces and one root package lock. Applications consume shared packages through named exports, not relative imports into another package's internals.
- Categorize Python tests into unit, integration, contract, and fixtures; browser tests live under `tests/e2e`. Add architecture guards for dependency directions and feature-local visual styling.
- Put operational code in `infrastructure`, development credential generation in `scripts`, ADRs under `docs/architecture/decisions`, and brewery-specific equipment/drawing/build-plan guidance under `docs/brewery`.
- Retain root `app.py` and `Dockerfile` as temporary production compatibility entrypoints. The root `compose.yaml` is development-only; it does not replace the Pi's root-owned Compose configuration. Publishing/deployment behavior remains unchanged until a separately controlled runtime replacement.

## Consequences

This is an M1 organization correction, not a new brewing feature or production deployment. It extends ADR-0001–ADR-0004 without changing their PostgreSQL/security decisions. All setup, package, migration, CI, and documentation links must point to their new owners. Existing historical verification statements remain historical. API health/readiness, migration behavior, secret isolation, and browser interactions must continue passing after the move. No brewing acceptance scenario is declared complete.
