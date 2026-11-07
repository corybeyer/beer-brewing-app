# ADR-0001: Modular monolith with explicit interfaces

Status: Proposed

## Context
Single Raspberry Pi hosts an advisory five-gallon all-grain brewery assistant. Small project with multiple independently growing brewery features.

## Decision
Favor one deployable application separated into domain capabilities, APIs, infrastructure adapters, and design system. Use ports/interfaces for persistence and telemetry. Do not introduce microservices initially.

## Consequences
Lower operations cost, easier testing, clear Codex edit boundaries. New protocols can be integrated without rewriting brewing rules. Review before adopting a different backend framework or splitting deployment units.
