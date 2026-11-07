# Docker

`api.Dockerfile` builds the separate development backend. Root `Dockerfile` remains the production smoke image until a controlled replacement. Root `compose.yaml` is development-only and uses per-service secret files. CI validates both ARM64 image builds.

## M1 runtime validation

Run `python3 scripts/development/check_containers.py` from the repository root with Docker daemon access and Compose v2. The `Container runtime` CI job runs the same check on native Linux x64; the existing ARM64 job separately builds both images.

The check builds the real development image, provisions fresh PostgreSQL roles, runs migrations, and waits for Docker health and HTTP readiness. It verifies that the non-root API receives only its read-only application secret and the database has no published port. It stops PostgreSQL to check that `/health` stays live while readiness returns sanitized HTTP 503, then verifies recovery. It removes/recreates containers and checks the PostgreSQL system identifier and migrated readiness against the retained volume. Finally, it builds/runs the retained root smoke image and checks its non-root user, HTTP payload, and Docker health.

Each run uses a unique Compose project, explicitly isolated network/volume, temporary generated passwords, and random loopback HTTP ports. Cleanup removes only that run's containers, test volume, network, and smoke image; development database volumes and saved `.secrets/` files are not used. Interrupted runs that bypass cleanup may leave resources prefixed `brewery-check-`; inspect them before removing anything manually.

These checks do not cover UI-to-container traffic, production frontend serving, Pi runtime, production deployment/rollback, or backup restoration (AC-14). No brewing acceptance scenario is completed. Production replacement remains a separate controlled change; see [production ownership](../deployment/production/README.md).
