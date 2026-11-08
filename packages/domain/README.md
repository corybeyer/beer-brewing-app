# Brewing domain

Owns brewing business rules, states, and abstract ports. It must not import web/API frameworks, database drivers, UI packages, sensor protocols, or infrastructure.

`brewery_domain.recipe_plan` implements the first M2 structural recipe rules: version-local links, combined dependency/anchor cycle detection, and exact same-unit portion totals. See the [validation specification](../../docs/requirements/recipe-plan-validation.md) for its typed interface and limits. `brewery_domain.recipes` defines the draft storage protocol, metadata values, validation, and conflict exceptions. The database package supplies its PostgreSQL adapter. No publication transition or brewing endpoint is implemented yet.
