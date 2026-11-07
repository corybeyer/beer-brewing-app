# Beer Brewing App

Locally hosted companion application for five-gallon all-grain brewing, running on a Raspberry Pi 5.

## Development context

Start with the [project knowledge base](docs/README.md) for [product scope](docs/requirements/product-scope.md), [current implementation status](docs/plan/status.md), [roadmap](docs/plan/roadmap.md), and [screen designs](docs/design/screens.md). The supplied manual prototype and wireframes are development references; they have not been integrated into the active health service.

## Project goals

- Manage recipes, instructions, reminders, and brew-day timers.
- Collect vessel-temperature readings with freshness and validity checks.
- Record manual measurements, additions, observations, and tasting notes.
- Preserve the recipe version used for each batch.
- Provide recommendations and alerts; the brewer operates burners, valves, pumps, and transfers.

## Delivery design

- **Pull request:** GitHub Actions runs tests and builds the Docker image.
- **Merge to `main`:** GitHub Actions reruns tests, builds and publishes an immutable, commit-tagged image to GitHub Container Registry (GHCR).
- **Production (future stage):** Raspberry Pi pulls approved image and deploys using Docker Compose, checks application health, and rolls back on failure.

This first commit is a deployment smoke-test foundation, **not the finished brewing application**. The minimal Python standard-library HTTP service will be replaced or expanded as the application architecture is decided.

## Local smoke test

The new development backend uses PostgreSQL 17, SQLAlchemy, Alembic, and FastAPI. See [backend setup and tests](docs/architecture/backend-foundation.md) to run the isolated development stack on localhost:8081. The root service below remains the production smoke test.

```sh
python3 -m unittest discover -s tests -v
python3 app.py
# from another terminal: curl http://localhost:8080/health
```

## Docker smoke test

```sh
docker build -t beer-brewing-app:local .
docker run --rm -p 8080:8080 beer-brewing-app:local
```

## Security

Never commit passwords, SSH keys, production data, personal access tokens, or `.env` files. Production data must live on persistent Raspberry Pi storage outside the application container.

## Repository

Public GitHub repository: https://github.com/corybeyer/beer-brewing-app
