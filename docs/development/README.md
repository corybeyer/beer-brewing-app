# Development workflow

Start with the [knowledge base](../README.md), [current status](../plan/status.md), [delivery gates](../plan/delivery-gates.md), and [ownership map](repository-layout.md). The current work is M2 recipe planning and the C1–C5 conversion slices. The foundation and manual draft/ingredient persistence are implemented; imports, publication, and brewing actions remain future work. Check source and branch state before choosing a task.

Before creating or updating any PR, run `python3 scripts/pre_pr.py` and verify the fresh report with `python3 scripts/pre_pr.py --verify-report`. See [required checks, policy rules, and limitations](pre-pr-validation.md). The fast architecture command is `python3 scripts/validate_repository.py`.

## Frontend

Use Node 24 LTS and run commands from the repository root:

```sh
npm ci
npm run dev
npm run build
```

Open http://127.0.0.1:5173 for the application. Home, Recipes, and Settings support refresh/back/forward navigation. Recipes supports stored draft listing, creation, overview editing, and ingredient editing with stale-edit review. Brew day/batch links, recipe search/filtering, publication, and imports remain unavailable. The standalone calculator is on a separate feature branch; see delivery gates before treating it as part of main. The page never fabricates recipe counts or sample recipes.

Open http://127.0.0.1:5173/component-examples.html for the repeatable shared-component gallery. Examples and component styles are owned by `packages/ui`, while tokens/icons/global foundations are owned by `packages/design-system`. The gallery is not part of the production bundle.

The web app's Vite server proxies `/api` to the development backend on localhost:8081. The typed client in communications validates readiness payloads, fails after five seconds, and cancels superseded requests. Connection status is refreshed on load, retry, reconnect, foregrounding, and every 30 seconds. This is service readiness, not a sensor freshness indicator or proof of loaded recipes. No database secret is passed to the browser. Vite's static preview server does not provide this development API proxy.

The development server's file access is limited to the web app, its three shared browser packages, and Node dependencies. Secret files, environment files, Git metadata, and backend source are not served; browser tests exercise those denials.

## Browser checks

```sh
npx playwright install chromium
npm test
```

On a Linux workstation with a compatible system Chromium, use `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm test`. CI installs its pinned Playwright Chromium and OS dependencies. Tests exercise desktop, tablet, and phone layouts, all routes, keyboard/focus/touch behavior, component states, timeouts/network/errors/retries, superseded responses, and axe WCAG A/AA checks.

Screenshots and failure traces are written to ignored `tests/e2e/test-results/`; CI uploads them as `frontend-browser-results`. Ready-service screenshots use mocked readiness responses and are visual test artifacts, not proof of a running database. Manually inspect screenshots in addition to automated accessibility checks.

Browser checks reserve localhost:5174 for a temporary test server; they do not reuse the localhost:5173 development server.

## Backend and database

See [backend setup](../architecture/backend-foundation.md) and [role/secret operations](../../infrastructure/deployment/database/README.md). Install the Python package, then run:

```sh
.venv/bin/python -m unittest discover -s tests -v
docker compose config --quiet
```

Supply `TEST_DATABASE_URL` for real PostgreSQL database/role tests; without it, those classes are explicitly skipped. Tests create/drop isolated databases and roles. Use TCP/SCRAM to test wrong-password rejection. Production credentials stay on the Pi; local `.secrets/` is ignored by Git and Docker builds.

The root smoke service remains independently runnable with `python3 app.py`. No frontend/static-serving change is deployed by local development commands.
