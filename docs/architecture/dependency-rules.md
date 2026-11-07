# Layer boundaries

The [workspace ownership map](../development/repository-layout.md) and [ADR-0005](decisions/0005-workspace-boundaries.md) assign these responsibilities to `apps/`, `packages/`, and `infrastructure/`. Shared controls belong in `packages/ui`; tokens, icons, and global foundations belong in `packages/design-system`. Feature CSS arranges those components rather than defining its own visual system.

| Layer | Owns | May depend on |
| --- | --- | --- |
| Domain modules | Brewing states, recipe rules, confirmations | Pure domain ports and utilities |
| Application services | Use-case coordination | Domain |
| API | Request parsing, response contracts | Application services |
| Persistence | Database records and migrations | Domain ports |
| Integrations | Sensor/MQTT/external protocol adapters | Domain ports, contracts |
| Frontend features | Screens and interaction | Design system, API clients |
| Design system | Tokens, assets, generic controls | No domain features |
| Infrastructure | Docker, GitHub, deployment | Deployable artifacts only |

Rules:
- Do not import infrastructure or transport into domain code.
- Do not call GitHub during normal brewery application runtime.
- Require manual confirmation for physical actions and stage transitions.
- Preserve timestamp provenance and a quality state for sensor measurements.
- Keep persisted state outside replaceable application containers.
