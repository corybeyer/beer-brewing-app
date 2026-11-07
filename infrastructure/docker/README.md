# Docker

`api.Dockerfile` builds the separate development backend. Root `Dockerfile` remains the production smoke image until a controlled replacement. Root `compose.yaml` is development-only and uses per-service secret files. CI validates both ARM64 image builds.
