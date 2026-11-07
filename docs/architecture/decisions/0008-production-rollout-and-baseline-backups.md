# ADR-0008: Staged production adoption and baseline database backups

Status: Proposed — November 7, 2026

## Context

The brewer requested connecting the tested UI/API candidate and PostgreSQL to production deployment. PR #7 builds/runs the candidate successfully, but the Pi still uses root-owned legacy Compose/configuration and a privileged deploy command. The development account cannot modify those files or access Docker. Deployment must not turn that limitation into a partial or unreviewed host replacement.

## Proposed decision

Publish three ARM64 images from the exact main commit after passing CI: the existing smoke image under its existing tag, the UI/API image under `app-sha-<commit>`, and the operator image under `operator-sha-<commit>`. Keep the existing SSH/deploy command until an administrator explicitly installs the reviewed production package. Retain original host Compose/environment/deployer files privately for legacy rollback; never import production configuration into source.

The new privileged deploy command accepts only a 40-character Git SHA, resolves application/operator images to registry digests, checks source-commit labels and baseline schema compatibility, and serializes operations. PostgreSQL has a dedicated persistent volume and no published port. Only assigned password files are mounted into each role. Provision and migrate explicitly, take a verified backup before migration, then run the application on a temporary loopback candidate port. Replace the production service only after candidate HTTP/readiness checks pass. On application failure, restore prior image/configuration; never automatically downgrade or restore the database.

Initially permit only the existing `0001_baseline` schema. Future revisions require an explicit reviewed compatibility policy, not an automatic assumption that every migration supports application rollback.

Store backups under `/var/backups/beer-brewing-app`, privately owned by root. Each set includes a custom-format database dump, required credential files, and revision/image metadata. Restore the dump into a uniquely named disposable verification database, compare its revision, row counts, and deterministic row-content fingerprints, then drop only that verification database. Publish a backup set only after verification; retain the newest seven verified sets. Run a persistent daily systemd timer and take a backup before each deployment. Frequent deployments may therefore shorten the time span covered by seven sets. Never replace the live database automatically during verification or rollout.

## Alternatives and limits

Immediately changing the root image tag would break the old deployment before its database configuration exists. A second long-running frontend proxy is unnecessary for the chosen same-origin application. Image rollback cannot reverse database changes.

Backups on the Pi's SSD support local rollback/operator recovery, not SSD-loss recovery. Off-device destination, encryption/transport, long-term retention, and whole-host restoration remain D-06/M4 decisions. This baseline verification does not claim AC-14's complete brewing-workflow restoration. Existing production port exposure is preserved; wider access and application authentication remain D-07 work.

## Adoption evidence

Use disposable-container tests to exercise real provisioning/migration, verified populated backups, candidate gating, HTTP health, retained data, and rollback. Installer tests must protect original files, secret preservation, private permissions, and refusal of unexpected host configuration. An administrator must explicitly install on the Pi; only then can the existing Actions command use the new deployment implementation. Record actual CI and host outcomes in current status.
