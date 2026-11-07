# API application

FastAPI composition and HTTP endpoints live in `brewery_api/api.py`. The development entrypoint is `brewery_api.api:create_app`. It composes `brewery_config` and `brewery_database`; domain rules and storage implementations stay out of handlers. Root `app.py` remains the production smoke service.

See [backend setup](../../docs/architecture/backend-foundation.md).
