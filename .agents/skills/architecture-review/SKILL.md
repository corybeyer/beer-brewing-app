---
name: architecture-review
description: Review proposed brewery code and designs for separation of concerns, contract stability, security, observability, and Raspberry Pi deployment safety.
---

# Architecture review
1. Identify changed layers and their dependency directions.
2. Confirm no domain import depends on runtime transport or UI framework.
3. Verify schema versioning, telemetry freshness semantics, and explicit physical-action confirmation.
4. Check secrets, Docker permissions, network boundaries, and data persistence.
5. Record material decisions as ADRs before implementing broad changes.
