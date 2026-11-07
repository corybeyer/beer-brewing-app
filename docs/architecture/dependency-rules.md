# Layer boundaries

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
