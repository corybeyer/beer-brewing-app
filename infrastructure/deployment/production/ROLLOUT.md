# UI/API production rollout

M1/UI-04 operations under [proposed ADR-0008](../../../docs/architecture/decisions/0008-production-rollout-and-baseline-backups.md) and the tested [ADR-0007 candidate](../../../docs/architecture/decisions/0007-production-serving-candidate.md). This is an administrator installation, followed by automatic event-driven releases. The recipe follow-up introduces only the reviewed draft schema under [proposed ADR-0010](../../../docs/architecture/decisions/0010-recipe-rollout-and-snapshot-backups.md); no physical equipment control is introduced.

## Before installation

Review the production Compose template, `install.py`, and `rollout.py` in this directory and the owning PR's CI. The `Production rollout and verified restore` job tests the real images in a disposable project, including populated backup restoration, failed-candidate rejection, legacy rollback, and retained data. Other CI jobs check ARM64 builds, live UI/API browser behavior, roles, migrations, and source policy. Root `app.py` and Dockerfile remain the legacy smoke image.

Publication now produces three tags for each validated main commit: `sha-<commit>` (legacy), `app-sha-<commit>` (UI/API), and `operator-sha-<commit>` (provision/migrate). The application and operator carry the source-commit label. Deployment resolves both to immutable digests. Until the administrator installs the new deployer, Actions continues using the original deployer and legacy image. Merging this PR alone does not activate PostgreSQL or the UI/API.

Wait for publication/deployment of the reviewed main commit to finish before one-time installation; do not merge another deployment while the installer is running. Update the local checkout to that exact reviewed main commit. Then, from the repository root, run:

```sh
sudo python3 infrastructure/deployment/production/install.py --commit FULL_MAIN_COMMIT_SHA
```

Replace `FULL_MAIN_COMMIT_SHA` with the full published merge SHA shown in Actions, not a PR head SHA. No password belongs in the command or chat. The local operating system may prompt the administrator for sudo authentication. The Codex development account currently cannot perform this root operation: `sudo -n` requires a password and Docker's socket denies access.

The installer refuses an unexpected host topology, writable/unowned legacy files, symlinks, unrelated administrative commands, or a pre-existing production volume without a matching staged installation. It recognizes the current one-service smoke Compose project and port 8080. It resolves both published images before changing host files. The root Compose and `.env` remain unchanged; private exact copies of them and the original deployer are retained in `/opt/beer-brewing-app/runtime/legacy-*`.

The reviewed Compose and standard-library deployer are installed privately under `/opt/beer-brewing-app/runtime`. Three independent password files are generated there with a private parent and read-only per-service mounts. The API receives only its application credential. No production credentials enter GitHub or source control. The new `/usr/local/sbin/brewery-deploy` keeps the existing SHA-only Actions/SSH contract and uses isolated Python execution. No sudoers, SSH, Tailscale, or public routing changes are made.

## Upgrading installed operations before the recipe release

The already installed baseline deployer rejects recipe images. After the PR's full CI passes and the exact source commit is reviewed, check out that commit in a **clean** repository and run from its root:

```sh
sudo python3 infrastructure/deployment/production/upgrade.py --commit FULL_REVIEWED_COMMIT_SHA
```

This operation installs deployment/backup code only; it does not run migrations, pull images, restart containers, change credentials, or modify the timer. It requires the exact reviewed clean commit, private owned installed files, unchanged Compose/launchers, intact legacy files, and either the known baseline operations hash or the exact current script. It rejects unrelated administrator changes. The existing deployment/backup lock excludes an active operation. The previous script is retained privately in `runtime/operations-history`; `runtime/operations.json` records the source commit and installed hash. Receipt-write failure restores the previous script; re-running the same reviewed update is safe. Do not replace root files manually or relax a failed preflight.

Perform this update **before merging** the recipe change. Then normal successful main CI/publication invokes the same SHA-only deploy command automatically. Do not merge/deploy concurrently with the administrator update. If publication occurred first, keep production on its baseline image and perform the reviewed updater before retrying the validated deployment. Do not widen the baseline script's gate by hand. This account still requires terminal sudo authentication for the root operation.

A fresh installation uses the current installer and current policy directly. The earlier `install.py` resume path intentionally refuses source differences in an already staged runtime; use `upgrade.py` for the reviewed installed-operations update.

## Upgrading installed operations before the catalogue release

`0003_fermentable_catalogue` adds four sourced, append-only catalogue tables under [proposed ADR-0012](../../../docs/architecture/decisions/0012-fermentable-catalogue.md). The installed recipe deployer accepts only baseline/recipe revisions and must be updated before this migration release merges. Wait for the catalogue PR's full CI (including real rollout/restore) to pass and review its exact source commit. From a clean checkout at that commit, run:

```sh
sudo python3 infrastructure/deployment/production/upgrade.py --commit FULL_REVIEWED_COMMIT_SHA
```

This uses the same guarded updater as the recipe release. It accepts the known baseline predecessor, the reviewed recipe script hash `545c7bcf971327a054981c6bbdd6c228f5b048808d147d13f3a68bb1e04790f4`, or the exact new script. It preserves all credentials, state, Compose, launchers, timer, and legacy fallback, and records/retains operations history. It does not migrate, deploy, restart services, or fetch images. Unknown/modified installed operations still require review; do not widen a failed gate manually. Check the private operations receipt and installed script hash against the reviewed source before merging. Administrator sudo authentication belongs in the terminal, never in source/chat.

After the root operations update, merge the reviewed schema PR. Main CI/publication invokes the existing SHA-only deployment automatically. Verify the resulting schema `0003_fermentable_catalogue`, four catalogue tables alongside retained recipe tables, source image label, `/health`, `/api/v1/readiness`, frontend serving, and a fresh verified snapshot backup. Catalogue tables start empty; no assumed manufacturer data is seeded. Whole-host/off-device recovery remains separate. If adoption fails after migration, a schema-incompatible recipe API is not restored; the retained smoke service can run until a corrected catalogue release succeeds.

## Startup and failure behavior

The deployment serializes with backups, permits only matching application/operator pairs for `0001_baseline`, `0002_recipe_drafts`, and `0003_fermentable_catalogue`, starts private PostgreSQL 17 on the persistent `brewery-production-postgres` volume, provisions roles, creates a verified pre-migration backup, and runs the explicit migrator. It then checks Docker health, `/health`, `/api/v1/readiness`, and `/` on a temporary loopback candidate before switching service `brewery` on port 8080.

Baseline accepts empty/baseline databases; recipe accepts empty/baseline/recipe databases; catalogue accepts empty/baseline/recipe/catalogue databases. Reverse catalogue-to-recipe/baseline and recipe-to-baseline transitions, unknown revisions, and mismatched pairs are rejected. The post-migration revision must match the application contract.

If a candidate or production switch fails, the prior UI/API is restored only if its declared revision matches the resulting database. A baseline API is incompatible after the recipe migration, and a recipe API is incompatible after the catalogue migration: in that case, or if the migration result cannot be determined, recovery uses the retained health-only smoke service. Schema adoption can briefly make the old API unavailable before cutover. A failed adoption may leave the smoke service running until a corrected recipe release succeeds. PostgreSQL and its volume are retained. No automatic schema downgrade or live database restore occurs. Future migrations require an explicit compatibility-policy update before this deployer will accept them. Preserve the root legacy image until controlled adoption passes.

On success, open `http://appHomebrew:8080/` (or the Pi's existing LAN address). `/health` remains liveness; `/api/v1/readiness` verifies the schema/database. Available recipe controls depend on the deployed image; catalogue authoring and conversion suggestions are not exposed by this storage slice. Existing port exposure is preserved; do not add public inbound access. D-07 authentication/concurrent-use decisions remain separate.

If initial rollout or timer setup fails, retain the failure output without copying credentials. Rerunning the same reviewed installer can resume when its installed operations exactly match source; it preserves credentials/data. Unexpected staged contents require administrator review. Do not delete the volume or regenerate credentials to fix authentication.

## Backups and recovery

`brewery-backup.timer` runs daily, with persistent catch-up and up to 15 minutes of jitter. Every deployment also takes a backup. Sets under `/var/backups/beer-brewing-app` are root-private and contain `database.dump`, private credential copies, and revision/image metadata. A read-only REPEATABLE READ psql transaction exports a snapshot; source revision and deterministic table-content fingerprints are read in that transaction, and `pg_dump --snapshot` finishes before it closes. The dump is restored into a generated `brew_verify_*` database and compared with those captured values before publication. Writes committed after the snapshot remain live but do not invalidate verification. Fingerprint formatting uses UTC and fixed numeric/date formatting. Snapshot sessions are bounded and closed on failure; no failed verification prunes prior sets. Only that scratch database is dropped. Failed verification never prunes prior sets.

Keep the newest seven verified sets; frequent deployments can shorten their calendar coverage. This is a local SSD policy, not protection against SSD loss. Off-device storage, encryption/transport, long-term retention, and whole-host recovery remain D-06/M4 work. The snapshot implementation covers the current relational recipe/catalogue tables under concurrent writes. It does not independently fingerprint roles, sequence counters, large objects, or host files; future capabilities must extend coverage when they introduce those data types. AC-14 is not marked complete.

Manual backup:

```sh
sudo /usr/local/sbin/brewery-backup
```

Application rollback to the retained legacy service:

```sh
sudo /usr/local/sbin/brewery-rollback-legacy
```

This retains PostgreSQL and backups. A subsequent normal release can adopt the UI/API again without losing data. Do not run `down -v`, change the PostgreSQL major, or restore a dump over the live database as an application rollback.

For disaster recovery, preserve a verified set and its credentials securely. An administrator must restore into a **new** PostgreSQL 17 volume/database, recreate matching roles from the saved credentials with the explicit operator, restore the custom dump with PostgreSQL 17 tools, validate revision/contents/permissions, then make a separate cutover decision. The tooling deliberately provides no unattended overwrite-live-database command. Test whole-host recovery and choose off-device retention before relying on this for future brew history.

## Disposable verification

With Docker access, from the repository root:

```sh
python3 -m scripts.development.check_production_rollout
```

This uses unique project/volume/image names, temporary synthetic credentials, and a random loopback port. Cleanup removes only those test resources. It never runs the root installer or reads production `.env`/password files. The expanded Docker check starts baseline and recipe contract fixtures, tests failed baseline-to-recipe and recipe-to-catalogue candidates with health-only recovery, adopts the catalogue API, creates runtime-role draft/catalogue fixtures, verifies their populated snapshot restore, rejects a reverse transition, and re-adopts with retained data. Fixtures reproduce baseline readiness/migration behavior; they are not claims about a historical published image. Local native PostgreSQL tests and mocked failure tests do not replace this Docker run or the actual Pi trial.
