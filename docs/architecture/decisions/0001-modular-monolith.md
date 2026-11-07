# ADR-0001: Modular monolith with explicit interfaces

Status: Accepted — November 7, 2026

## Context
Single Raspberry Pi hosts an advisory five-gallon all-grain brewery assistant. Small project with multiple independently growing brewery features.

## Decision
Favor one deployable application separated into domain capabilities, APIs, infrastructure adapters, and design system. Use ports/interfaces for persistence and telemetry. Do not introduce microservices initially.

## Consequences
Lower operations cost, easier testing, clear Codex edit boundaries. New protocols can be integrated without rewriting brewing rules. Review before adopting a different backend framework or splitting deployment units.

The accepted [PostgreSQL foundation](0003-postgresql-foundation.md) specifies FastAPI, the `brewery` package/entrypoint, and the boundary between the development backend and the retained production smoke service.
