# Existing production deployment

Production uses an event-driven GitHub Actions -> Tailscale OIDC -> SSH brewdeploy -> root-owned /usr/local/sbin/brewery-deploy -> Docker Compose chain.

Authoritative running configuration lives on the Raspberry Pi:
- /opt/beer-brewing-app/compose.yaml
- /opt/beer-brewing-app/.env
- /usr/local/sbin/brewery-deploy

Do not overwrite this configuration from scaffolding. Propose future deployment-script source control as a separate, carefully reviewed change, with health checks, backup, and rollback tests.
