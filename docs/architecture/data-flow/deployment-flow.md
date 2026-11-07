# CI/CD flow

```mermaid
flowchart LR
  Codex["Codex edits feature branch"] --> PR["Pull request"]
  PR --> Check{"CI checks pass?"}
  Check -->|No| Fix["Fix tests/code"]
  Fix --> PR
  Check -->|Yes + review| Merge["Merge to main"]
  Merge --> MainCI["Main CI tests + ARM64 build"]
  MainCI --> Publish["Publish commit-tagged image to GHCR"]
  Publish --> OIDC["GitHub Actions + Tailscale OIDC"]
  OIDC --> SSH["SSH brewdeploy on Pi"]
  SSH --> Script["Restricted root-owned deployment script"]
  Script --> Pull["Pull + pin image digest"]
  Pull --> Healthy{"Container healthy?"}
  Healthy -->|Yes| Done["Release live"]
  Healthy -->|No| Rollback["Restore previous image"]
```

Actual workflow files: .github/workflows/ci.yml and publish.yml. Deploy script is installed on the Pi at /usr/local/sbin/brewery-deploy; proposed infrastructure/deployment/ sources must not overwrite it without separate validation.

This mechanism is event-driven. Production does not poll GitHub or GHCR for releases.
