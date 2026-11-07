# Infrastructure instructions

- Preserve .github/workflows/ci.yml and publish.yml semantics unless the change specifically targets CI/CD.
- Production is Raspberry Pi 5, Linux arm64, Docker Compose, with GHCR immutable-image deployment over Tailscale and restricted SSH.
- No periodic production polling and no public inbound SSH or router port forwarding.
- Do not commit private credentials, personal SSH keys, root-owned host .env, or runtime data.
- Deployment changes must document rollback, health checks, and stateful-data safety.
- Never assume Docker socket access is limited; treat it as root-equivalent.
