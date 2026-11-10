# Current delivery gates

Source checkpoint: `main` at `1af3ad94f8c8d8524980e310d6925336deb6d2c2` (PR #19). This is a review snapshot, not a live Pi status report. Refresh Git refs before choosing the next task; an older local checkout is not evidence that merged work is missing.

## Work state

| Slice | Source state | Next gate |
| --- | --- | --- |
| Foundation and manual recipe editing | Merged: FastAPI/React/PostgreSQL foundation, overview and ingredient editing, optimistic conflicts, migrations, and operational tooling | Continue M2; preserve remaining recovery requirements rather than restarting M1 |
| C1 exact conversion | Merged in PR #14 | Reuse its domain arithmetic in owning features |
| C2a fermentable catalogue | Merged/deployed in PR #16; host and snapshot evidence is in [current status](status.md#verified-production-catalogue-adoption) | No new host-adoption claim from this review |
| C2b immutable proposal domain | Merged in PR #17 | Transactional retention and later Apply are distinct operations |
| C2b transactional proposal storage | [Draft PR #18](https://github.com/corybeyer/beer-brewing-app/pull/18), `d3858c7945aeff5c26cc94c04191668585b655a7` | Review plus verified administrator operations update before merge; schema adoption and a fresh verified backup after deployment |
| C3 grain ranking / selected-blend sizing | Merged in PR #19 at `1af3ad9` | Blend snapshot-format extension, proposal integration, and feasibility/diastatic review remain; no picker/Apply yet |
| C5 standalone conversion calculator | Remote branch `feat/conversion-calculator`, `6272ba09bb3eec23b65e67b0954a5c7026116eb1` | Bring current main into the feature branch, run full source-bound pre-PR checks, review, and independent CI before merge; no schema/operations update required |

Recipe step editing, publication/revisions, classification, targets, complete M2 acceptance, and the simulated brew workflow remain owning-feature work. C4 picker/Apply must recheck the current draft atomically and preserve/remap step links. Off-device/whole-host recovery and complete AC-14 remain outstanding.

## Proposal-storage release gate

The public [PR CI #40 summary](https://github.com/corybeyer/beer-brewing-app/actions/runs/42628293075) identifies source `d3858c7` and reports Success for all eight jobs, including real rollout/restore and ARM64 builds. PR #18 is still Draft. A successful CI run does not establish that installed operations on the Pi were updated.

The branch's `infrastructure/deployment/production/ROLLOUT.md`, section “Upgrading installed operations before the proposal-retention release,” requires an administrator to use the exact clean reviewed source after CI/review:

```sh
sudo python3 infrastructure/deployment/production/upgrade.py --commit d3858c7945aeff5c26cc94c04191668585b655a7
```

This command belongs on the production host in the clean checkout of that exact commit, after its source review. It is documented here, not executed by this review. Confirm the installed script hash and private receipt against that source before merging. If the PR source changes, review it again and replace the commit above; do not reuse evidence for a different revision.

The updater preserves credentials/state and does not itself migrate or restart the app. After merge, the normal deployment must verify image source, revision `0004_conversion_proposals`, retained recipe/catalogue data, health/readiness/frontend, and a fresh verified snapshot backup. Preserve rejection of unknown/reverse/mismatched schema pairs and the retained smoke fallback. No administrator update, production merge, migration, or host verification was performed in this review.

## Local review evidence

The branches were checked separately without changing their source:

- **Proposal storage, `d3858c7`:** repository policy passed; 91 focused domain/codec/PostgreSQL/role/migration/backup/operations tests passed. The database was disposable PostgreSQL 17 over TCP/SCRAM. Backup clients used the supported `POSTGRES_TEST_BIN` override with wrappers invoking that container's PostgreSQL tools. Initial container-client checks could not launch because the fixture assumes `/usr/bin/docker`; using the override resolved all seven setup errors without code edits. This is local storage/restore evidence, separate from the successful CI container/ARM64 coverage.
- **Calculator, `6272ba0`:** 10 API/contract tests, the TypeScript/Vite production build, and 24 Playwright checks passed across desktop/tablet/phone. Desktop and phone screenshots were visually inspected. Browser checks use mocked conversion/readiness responses; backend tests separately execute the real endpoint. This is not a real-browser-to-backend integration run, a complete source-bound pre-PR report, or production adoption. No current calculator CI/PR status is claimed.

The GitHub API connection was denied by the environment proxy. The CI result above was verified from GitHub's public HTML summary instead. Repository Git reads/writes are a separate capability from GitHub API access.

## Immediate sequence

1. Complete PR #18's source review and verify the administrator operations update before its schema merge. Keep it draft until that prerequisite is evidenced.
2. Independently prepare the calculator branch against latest main and run the [required pre-PR gate](../development/pre-pr-validation.md), including disposable database coverage. Its basic conversion tool does not depend on the proposal-storage release.
3. Integrate C3 blend results into an explicitly versioned proposal format before building C4 picker/Apply. Keep individual reviewable changes scoped to their owning layer.
4. Update this checkpoint and [current status](status.md) when source, CI, merge, or host evidence changes. Preserve historical evidence with its exact source identity.
