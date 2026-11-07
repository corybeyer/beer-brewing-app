# Architecture decision records

| Record | Status | Topic |
| --- | --- | --- |
| [ADR-0001](0001-modular-monolith.md) | Accepted | Modular monolith and explicit interfaces |
| [ADR-0002](0002-presentation-system.md) | Proposed | Shared presentation system |
| [ADR-0003](0003-postgresql-foundation.md) | Accepted | PostgreSQL and isolated backend foundation |
| [ADR-0004](0004-database-roles-and-secrets.md) | Accepted | Separate database roles and host-held credentials |

See [open decisions](../plan/open-decisions.md) for outstanding choices. Preserve existing statuses until a decision is explicitly accepted; the prototype's implementation is not automatic approval of its architecture.

For a new material decision, add the next numbered Markdown file with: title, status (Proposed / Accepted / Superseded), context, decision, alternatives considered, consequences, and links to affected specifications. Include a decision date when accepted. When superseding a record, retain it and link both directions rather than erasing rationale.

Keep runtime instructions in the project README/setup documentation, product behavior in requirements, and implementation progress in [current status](../plan/status.md).
