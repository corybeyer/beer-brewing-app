# Project knowledge base

Start here before planning or implementing a feature. This knowledge base combines the repository foundation, the supplied manual prototype, and the wireframe go-bys. Documentation added on November 7, 2026 (America/Chicago).

## Reading path

1. [Product scope](requirements/product-scope.md): intended brewing workflow and boundaries.
2. [Current status](plan/status.md): what is implemented and what has actually been verified.
3. [Roadmap](plan/roadmap.md): delivery order, acceptance criteria, and the next task.
4. [Open decisions](plan/open-decisions.md): choices that must remain explicit.
5. Read the relevant [screen specification](design/screens.md), [acceptance scenarios](requirements/acceptance-scenarios.md), [architecture](architecture/system-overview.md), and [decision records](architecture/decisions/README.md).

## Documentation map

| Area | Owns |
| --- | --- |
| [Requirements](requirements/README.md) | Product behavior, integrity rules, and acceptance scenarios |
| [Recipe-plan rules](requirements/recipe-plan-validation.md) | First M2 domain slice: version-local references, combined graph validation, and ingredient portions |
| [Conversion proposal snapshots](requirements/conversion-proposal-snapshots.md) | Immutable C2b domain inputs, exact evidence, and review-time stale checks |
| [Conversion proposal retention](architecture/conversion-proposal-storage.md) | Transactional historical documents, save-time revision locking, and guarded migration rollout |
| [Extract conversion plan](plan/extract-conversion.md) | Sourced formulas, calculator assumptions, grain-match picker, delivery slices, and verification cases |
| [Recipe draft storage](architecture/recipe-draft-storage.md) | Development recipe schema, transactions, concurrency, and guarded migration rollout |
| [Fermentable catalogue storage](architecture/fermentable-catalogue.md) | Immutable sourced grain/DME/LME profiles, exact compositions, catalogue migration, and rollout |
| [Architecture](architecture/system-overview.md) | Components, [dependency boundaries](architecture/dependency-rules.md), [target data model](architecture/data-model.md), and deployment topology |
| [Backend foundation](architecture/backend-foundation.md) | PostgreSQL development stack, migrations, health contracts, and tests |
| [Development](development/README.md) | Workspace setup, [package ownership](development/repository-layout.md), frontend gallery, and categorized tests |
| [Design](design/screens.md) | Screen behavior, [design principles](design/design-principles.md), and [wireframe guidance](design/wireframes/README.md) |
| [Development images](images/README.md) | Screenshots and visual guidance for development tasks |
| [Decisions](architecture/decisions/README.md) | Architectural rationale and decision status |
| [Plan](plan/roadmap.md) | Milestones, current status, and unresolved decisions |
| [References](references/README.md) | Preserved source material and historical evidence |
| [Contracts](../packages/communications/contracts/README.md) | Versioned machine-readable communication interfaces |

## How to interpret status

- **Implemented:** present in the active application, with evidence linked in current status.
- **Reference prototype:** exists in the supplied prototype; integration and verification in this repository are separate work.
- **Target requirement:** intended product behavior; not an implementation claim.
- **Proposed:** a choice awaiting an explicit decision.
- **Deferred:** intentionally outside the current milestone.

Historical references preserve earlier statements, dates, and setup commands. They do not override the curated plan. The newer repository baseline is Raspberry Pi 5, 16 GB RAM, SSD, and application port 8080. Any unresolved conflict belongs in [open decisions](plan/open-decisions.md); do not silently resolve it by copying prototype code.

## Keeping context useful

- Keep each fact in its owning document and link to it elsewhere. Archived source files remain unchanged.
- Feature tasks and PRs should cite their milestone, screen ID, and acceptance scenario IDs.
- Update current status and affected specifications alongside implementation. Mark a scenario passed only with a test/run reference and an explanation of what was exercised.
- Record broad architectural decisions in an ADR before implementation; include status, context, choice, consequences, and links to superseded decisions when relevant.
- Keep `AGENTS.md` concise: development rules and links to this reading path. Keep task scratch notes and secrets out of the knowledge base.
- Do not infer hardware status, deployed behavior, completed tests, or approved technology choices from a wireframe or reference archive.
