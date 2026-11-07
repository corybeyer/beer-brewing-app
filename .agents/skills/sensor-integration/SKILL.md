---
name: sensor-integration
description: Add or change temperature and telemetry sources while preserving transport independence, timestamps, validation, and safe brewing recommendations.
---

# Sensor integration
1. Read packages/communications/contracts/sensors/ and relevant ADRs.
2. Implement transport adapters behind the domain-facing sensor port.
3. Preserve measured_at, received_at, device_id, units, and reading status.
4. Deduplicate events; bound retries and handle offline behavior.
5. Add simulator fixtures for missing, late, duplicate, and implausible data.
6. Never trigger burners, pumps, or stage transitions from telemetry.
