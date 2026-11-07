# ADR-0002: Shared design system

Status: Accepted — November 7, 2026

## Decision
Use semantic CSS tokens, approved typography and icons, reusable accessible components, and consistent responsive layouts. Put reusable controls and examples under `packages/ui/`, visual foundations under `packages/design-system/`, and screen composition under `apps/web/src/features/`, per [ADR-0005](0005-workspace-boundaries.md).

The brewer approved implementing the React/TypeScript frontend foundation after PR #4. Use Vite with React and TypeScript, Node 24 LTS for development/CI, system fonts (no external font requests), and MIT-licensed Lucide icons. Keep the package lock in source control. Use Playwright browser tests with axe accessibility checks and exported desktop/tablet/phone screenshots for visual review.

The first API client is a small typed adapter for version 1 readiness with runtime payload validation, request timeout/cancellation, and explicit checking/ready/unavailable states. Proxy `/api` through the local Vite development server to the backend on localhost:8081; the browser uses same-origin requests, without adding CORS or database credentials. Revisit generated clients when business APIs are introduced.

Use hash-based navigation for the initial Home, Recipes, and Settings views so refresh and browser history work without production routing changes. Keep unimplemented brew-day/batch navigation and recipe controls visibly unavailable. The Recipe Library (UI-04) is a foundation/empty-state view; do not fabricate recipe data or interpret backend readiness as proof of an empty library. No recipe storage, import, or brewing action is provided by this milestone.

The frontend runs separately on localhost:5173 and builds static assets into ignored `apps/web/dist/`. Root `app.py`, production Docker packaging, and deployment remain unchanged. Production serving/integration requires separate container/runtime verification; this work does not complete M1 or AC-01/AC-03/AC-13.

## Requirements
Maintain accessible contrast, visible focus, large mobile touch targets, statuses not conveyed by color alone, and clear temperature units/freshness. Visual change reviews should compare screenshots/story examples.
