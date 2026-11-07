# Existing production deployment

Production uses an event-driven GitHub Actions -> Tailscale OIDC -> SSH brewdeploy -> root-owned /usr/local/sbin/brewery-deploy -> Docker Compose chain.

Authoritative running configuration lives on the Raspberry Pi:
- /opt/beer-brewing-app/compose.yaml
- /opt/beer-brewing-app/.env
- /usr/local/sbin/brewery-deploy

Do not overwrite this configuration from scaffolding. Propose future deployment-script source control as a separate, carefully reviewed change, with health checks, backup, and rollback tests.

## M1 replacement gates

The current production image serves only `/health` on port 8080. The development API listens on 8081, requires database configuration, and does not serve the built frontend. Vite's development proxy is not a production server. The present deployment cannot adopt the new runtime merely by changing its Python entrypoint.

Before proposing replacement, record a serving/topology decision covering built frontend assets, same-origin `/api` routing, port 8080 compatibility, non-root permissions, and liveness versus database readiness. Validate the UI against the real API through that serving path, including database failure. Preserve the current root image and deployment until those checks pass.

Separately review the Pi-owned Compose/deploy configuration, provision host-held credentials and persistent PostgreSQL storage, and define one explicit migration operation before startup. Document backup/restore and retained-data compatibility before any stateful deployment; image rollback must not automatically downgrade the database. A controlled ARM64 trial must verify HTTP/Docker health and rollback using the immutable image digest. The [disposable container check](../../docker/README.md) supplies development evidence only and does not inspect or modify the Pi.
