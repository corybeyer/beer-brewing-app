# Repository ownership and dependency rules

Decision: [ADR-0005](../architecture/decisions/0005-workspace-boundaries.md). The directory structure separates concerns; dependencies and review rules enforce that separation.

| Owner | Responsibility | Allowed dependencies |
| --- | --- | --- |
| `apps/web` | Browser composition, routes, screen layout, React state | Public UI/design-system/communications exports |
| `apps/api` | FastAPI composition and HTTP endpoints | Domain/services, database adapter, configuration |
| `packages/ui` | Shared React controls, component styles, repeatable visual examples | Design system, React |
| `packages/design-system` | Semantic colors, typography, spacing, icons, global foundations | Licensed icon assets; no application/UI imports |
| `packages/domain` | Pure brewing rules, states, and ports | Pure shared validation; no frameworks, drivers, or protocols |
| `packages/database` | Database adapter, future models/repositories, versioned migrations | Database tooling, domain ports, configuration for migration bootstrap |
| `packages/integrations` | Future sensor/external adapters | Domain ports, communications, validation |
| `packages/communications` | Versioned transport contracts and readiness HTTP adapter | Browser fetch; no React or UI imports |
| `packages/config` | Environment/credential parsing | Configuration tooling; no application workflows |
| `packages/validation` | Future reusable pure validation | No framework, driver, or infrastructure imports |
| `infrastructure` | Docker, Pi operations, provisioning, deployment, monitoring | Deployable artifacts; never imported by runtime API/domain |
| `scripts` | Setup/maintenance commands | Owning public interfaces; no embedded credentials |

Some packages currently contain ownership documentation only. No sensors, domain rules, or generic validation are invented to populate the tree.

Python source mappings in root `pyproject.toml` install `brewery_api`, `brewery_database`, and `brewery_config`. Root npm workspaces expose `@brewery/ui`, `@brewery/design-system`, and `@brewery/communications`; consumers use package exports instead of relative paths across packages. Keep a single root npm lock.

Feature CSS arranges shared components using semantic layout/spacing tokens. New colors, fonts, reusable control states, empty states, and icon treatments belong in their shared owners. The repeatable component gallery is `packages/ui/src/examples/Gallery.tsx`; `docs/images/` holds development references. The browser gallery entrypoint is development-only and is not bundled into the product.

Tests are grouped into `tests/unit`, `tests/integration`, `tests/contract`, `tests/e2e`, and `tests/fixtures`. The [repository validator](pre-pr-validation.md) and negative/positive regression fixtures enforce the reviewable ownership/import/style policy. The pre-PR command also runs functional, build, and browser checks. These checks supplement code review; they do not prove every architectural rule automatically.

ADRs live under `docs/architecture/decisions`; network/data-flow diagrams have separate folders. Brewery equipment, drawings, and build plans belong under `docs/brewery`. New documentation starts at [the knowledge base](../README.md).

Root `app.py` and `Dockerfile` are temporary production compatibility entrypoints. Root `compose.yaml` is development-only. They preserve the current health service and deployment while new application serving is reviewed and validated separately.
