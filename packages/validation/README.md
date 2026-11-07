# Shared validation

Owns reusable pure validation rules that have more than one consumer. Domain invariants remain owned by the domain; request parsing stays in API adapters and credential parsing in configuration. This package has no runtime rules yet and must not import application frameworks or database drivers.
