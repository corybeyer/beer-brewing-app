# Monitoring

Root `/health` remains the production smoke check. The separate backend exposes `/api/v1/readiness` for database/schema readiness. Additional host/container monitoring is not implemented by this scaffold and must remain outside brewing business rules.
