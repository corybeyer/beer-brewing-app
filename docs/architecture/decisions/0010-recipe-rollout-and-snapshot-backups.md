# ADR-0010: Recipe-schema rollout and synchronized backup verification

Status: Proposed — November 7, 2026

## Context

ADR-0008's installed deployer permits baseline only. ADR-0009 introduces `0002_recipe_drafts`; an old baseline API cannot report ready after that migration. Comparing a dump with independently sampled live tables also fails under concurrent writes. The privileged operations script needs an explicit administrator update before this feature merges.

## Proposed decision

Permit only matching application/operator revision pairs in the explicit set `0001_baseline`, `0002_recipe_drafts`. Baseline accepts empty/baseline databases; recipe accepts empty/baseline/recipe databases. Reject unknown revisions, mismatched image pairs, reverse schema transitions, and incompatible previous images before migration. Require a verified pre-migration backup, explicit migrations, resulting-revision verification, candidate health/readiness/UI checks, then production cutover.

If a candidate/switch fails after schema change, restore the previous UI/API only when its exact declared revision matches the resulting database. Otherwise restore the retained legacy smoke service, preserving PostgreSQL, backups, and credentials. Never downgrade the schema or restore over the live database. In-place baseline-to-recipe adoption can briefly make the old API unavailable; failure may intentionally leave health-only service until a corrected recipe release is adopted.

Keep a read-only REPEATABLE READ transaction open in psql, export its snapshot, and calculate source revision/table fingerprints in that transaction. Run `pg_dump --snapshot` before ending it. Restore into a fresh scratch database and compare to the captured snapshot values, independent of later writes. Failures publish/prune nothing; bounded processes and explicit transaction cleanup prevent abandoned snapshot sessions. This is database/table verification, not whole-host recovery or full AC-14.

Provide an administrator-only operations updater for the reviewed clean commit, serialized with deployment/backup. Accept only the exact known predecessor or current operations hash, unchanged Compose/launchers, private owned installation files, intact legacy artifacts, and existing credentials. Preserve the prior script privately, replace only `runtime/rollout.py` atomically, and retain all runtime state/configuration/credentials. Root operations must be updated from the reviewed PR commit before merge; normal validated-main publication/deployment remains event-driven with its existing SHA-only entrypoint. No sudoers, routing, or secret changes.

## Evidence and remaining scope

Test concurrent real PostgreSQL writes during dump/verification, scratch cleanup, retention, failure cleanup, explicit schema transition/fallback cases, and updater preservation/refusal/idempotence. Extend disposable Docker rollout CI to exercise baseline-to-recipe adoption, broken-candidate recovery after migration, and re-adoption with retained data. Native tests do not replace container/ARM64 CI or the administrator operation and controlled Pi adoption. Existing proposed ADR statuses remain proposed.

## References

- [PostgreSQL 17 snapshot synchronization](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-SNAPSHOT-SYNCHRONIZATION)
- [PostgreSQL 17 pg_dump snapshot option](https://www.postgresql.org/docs/17/app-pgdump.html)
