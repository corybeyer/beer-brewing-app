# Communications

Owns versioned transport contracts under `contracts/` and the typed browser readiness adapter in `src/readiness.ts`, exported as `@brewery/communications`. React state/hooks stay in `apps/web`; the transport package imports neither React nor app features.

The sensor schema retains its original `$id` as a stable contract identifier despite the file relocation. MQTT/WebSocket adapters are not implemented or selected by this directory. See [contracts](contracts/README.md).
