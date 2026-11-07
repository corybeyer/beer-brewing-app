---
name: testing
description: Build and run automated tests for brewery domain rules, API contracts, UI components, sensors, and Docker health/deploy safety.
---

# Testing
1. Read current CI checks before adding tooling.
2. Cover success, missing data, invalid input, stale data, and edge cases.
3. Use deterministic fixtures and simulation instead of live brewery hardware.
4. Ensure /health and the ARM64 image still build.
5. Report what ran and what remains unverified.
