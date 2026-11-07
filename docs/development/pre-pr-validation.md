# Repository policy and pre-PR checks

M1 tooling under [ADR-0006](../architecture/decisions/0006-pre-pr-validation.md). The goal is repeatable separation-of-concerns enforcement, not just a folder convention.

## Required command before every PR

From the repository root:

```sh
python3 scripts/pre_pr.py
python3 scripts/pre_pr.py --verify-report
```

Run the first command after the final source edit. The second checks that the successful report still matches the current source and base commit immediately before creating or updating the PR. Both commands exit nonzero on failure. Nothing is published, merged, or deployed.

Prerequisites: Python 3.12+, the installed backend virtual environment, Node 24, root `npm ci`, and a Playwright Chromium installation (`npx playwright install chromium`). On a Linux development machine with compatible system Chromium, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium` before running the command. The tool does not download tools, ask for production credentials, or alter Docker permissions.

The command runs repository policy checks, frontend validator regression fixtures, Python tests, TypeScript/Vite production build, and browser/component/accessibility checks. Local results go into ignored `.validation/pre-pr.json` with a source fingerprint and check statuses, never environment/credential values.

Browser tests start their own temporary server on localhost:5174 and never reuse an existing development server. Leave that port free. Your normal localhost:5173 development server can remain running.

Provide `TEST_DATABASE_URL` for a disposable PostgreSQL instance with database/role creation permissions to include integration tests. Without it, the Python suite explicitly skips database classes and the report prints **NOT VERIFIED**. To require database and TCP password-authentication coverage locally:

```sh
python3 scripts/pre_pr.py --require-database
python3 scripts/pre_pr.py --verify-report --require-database
```

Never point tests at a production database. This command does not substitute the normal application `DATABASE_URL` or read saved `.secrets/` credentials to obtain a test connection. Unix-socket tests do not claim TCP password-authentication coverage. CI independently provides disposable TCP/SCRAM PostgreSQL.

## Fast checks while coding

```sh
python3 scripts/validate_repository.py
python3 scripts/validate_repository.py --json
```

This checks the entire Git-visible working snapshot, including new untracked source files, while ignoring generated/local files according to Git. Removed paths are absent. It parses source without importing or executing application code. Parser/setup errors fail validation instead of silently skipping frontend checks.

## Enforced rules

| Area | Checks |
| --- | --- |
| File ownership | Approved root files, declared app/package owners, source language placement, categorized tests, one npm lock, contracts and migrations in their owning directories |
| Python boundaries | Allowed package directions and external imports, literal/computed dynamic imports, relative package escape, centralized environment reads, DDL outside handlers |
| Browser boundaries | Import/type-import/export/require/dynamic-import directions, public exports, declared dependencies, workspace registry, missing export targets, dependency cycles |
| Shared presentation | Screens use library controls/icons rather than native replacements or SVGs; no screen-local style/sx/css/palette props; feature CSS is layout-only |
| Tokens | No literal palette/dimensions outside token definitions, missing tokens, feature-local token definitions, external stylesheet imports, or undocumented breakpoints |
| Transport/configuration | HTTP fetching stays in communications; browser environment handling needs a central configuration adapter; runtime code cannot import provisioning/deployment tooling |
| Database integrity | Literal/unique migration revisions, valid parents, no cycles/divergent heads, readiness revision matching the migration head |
| Source hygiene | Sensitive/runtime/generated filenames outside Git; known private-key/token patterns; Git/Docker secret exclusions; valid JSON and active documentation file links |

Python uses its standard AST; frontend checks use Babel's TypeScript/JSX parser and PostCSS. Comments and strings that merely describe imports/controls do not become executable violations. Secret findings report locations and rule IDs without printing matched values. Archived `docs/references/` code is treated as reference material and is not executed or reinterpreted as active architecture.

## Policy, exceptions, and CI

The reviewable source of truth is [policy.json](../../scripts/validation/policy.json). Add a new concern or dependency deliberately, with ownership/ADR updates, rather than weakening a rule until a misplaced file passes. Runtime policy graphs cannot use wildcard dependencies or cycles.

An exception needs an exact existing path, known rule, meaningful reason, and an existing accepted ADR. Wildcard and inline suppressions are unsupported. Secret/generated-file and parser/tool failures cannot be waived. Exceptions are reported through the policy diff and require normal review; the tool cannot stop someone from deliberately changing its own implementation.

The `Repository policy` CI job runs the same checker and regression fixtures on PRs/main. Existing backend, frontend, and ARM64 jobs remain independent. To prohibit merging on a failed check, configure GitHub branch protection/rulesets to require these statuses. That administrative setting is not changed by this tool. PR creation outside the documented workflow can bypass the local command; CI is the independent backstop. No Git hook is installed automatically.

## What still needs review

Static checks cannot reliably infer arbitrary business purpose, prove that a calculation belongs in a particular domain capability, catch every indirect/dynamic dependency or secret, judge visual quality, establish sensor/hardware correctness, or validate container secret mounts and production deployment. They do not prove compatibility of an irreversible database migration or replace acceptance scenarios. Browser axe checks also do not prove all accessibility requirements.

Continue human architecture/visual review and meaningful feature tests. Keep the source report current and disclose missing database/container/deployment evidence in the PR.
