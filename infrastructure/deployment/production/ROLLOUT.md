# UI/API production rollout

M1/UI-04 operations under [proposed ADR-0008](../../../docs/architecture/decisions/0008-production-rollout-and-baseline-backups.md) and the tested [ADR-0007 candidate](../../../docs/architecture/decisions/0007-production-serving-candidate.md). This is an administrator installation, followed by automatic event-driven releases. No physical equipment control or business schema is introduced.

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

## Startup and failure behavior

The deployment serializes with backups, permits only the explicitly reviewed `0001_baseline` schema, starts private PostgreSQL 17 on the persistent `brewery-production-postgres` volume, provisions roles, creates a verified pre-migration backup, and runs the explicit migrator. It then checks Docker health, `/health`, `/api/v1/readiness`, and `/` on a temporary loopback candidate before switching service `brewery` on port 8080.

Failed candidates do not replace production. If the production switch fails, the prior application configuration/image is restored; on initial adoption it restores the legacy service. PostgreSQL and its volume are retained. No automatic schema downgrade or live database restore occurs. Future migrations require an explicit compatibility-policy update before this deployer will accept them. Preserve the root legacy image until controlled adoption passes.

On success, open `http://appHomebrew:8080/` (or the Pi's existing LAN address). `/health` remains liveness; `/api/v1/readiness` verifies the schema/database. The UI remains the current recipe preview with disabled recipe operations. Existing port exposure is preserved; do not add public inbound access. D-07 authentication/concurrent-use decisions remain separate.

If initial rollout or timer setup fails, retain the failure output without copying credentials. Rerunning the same reviewed installer can resume when its installed operations exactly match source; it preserves credentials/data. Unexpected staged contents require administrator review. Do not delete the volume or regenerate credentials to fix authentication.

## Backups and recovery

`brewery-backup.timer` runs daily, with persistent catch-up and up to 15 minutes of jitter. Every deployment also takes a backup. Sets under `/var/backups/beer-brewing-app` are root-private and contain `database.dump`, private credential copies, and revision/image metadata. Each dump is restored into a generated `brew_verify_*` database; revision and deterministic table-content fingerprints must match before publication. Only that scratch database is dropped. Failed verification never prunes prior sets.

Keep the newest seven verified sets; frequent deployments can shorten their calendar coverage. This is a local SSD policy, not protection against SSD loss. Off-device storage, encryption/transport, long-term retention, and whole-host recovery remain D-06/M4 work. The current read-only foundation permits deterministic source/restore comparisons; business write APIs must introduce consistent-snapshot semantics before this comparison is reused under concurrent writes. AC-14 is not marked complete.

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

This uses unique project/volume/image names, temporary synthetic credentials, and a random loopback port. Cleanup removes only those test resources. It never runs the root installer or reads production `.env`/password files. Local native PostgreSQL dump/restore tests and mocked failure tests do not replace this Docker run or the actual Pi trial.
