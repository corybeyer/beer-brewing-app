# ADR-0006: Repeatable repository and pre-PR validation

Status: Accepted — November 7, 2026

## Decision

Provide `python3 scripts/pre_pr.py` as the required local command before creating or updating a PR. It runs repository policy validation, validator regression tests, Python tests, frontend type/build checks, and browser/accessibility checks. PostgreSQL integration tests run when `TEST_DATABASE_URL` is supplied; otherwise the report explicitly records the missing integration coverage. `--require-database` makes that omission fail locally. CI continues to require its independent PostgreSQL job.

Keep ownership and dependency rules in `scripts/validation/policy.json`. Use Python AST for Python and Babel/PostCSS parsers for TypeScript/JSX/CSS rather than matching code-shaped text in comments. Reject unknown owners, forbidden dependency directions, private cross-package imports, misplaced tests/contracts/migrations, feature-local presentation, and known sensitive/generated files entering Git. Protect local secret exclusions and check active documentation links.

Run repository policy and regression checks as a separate CI job. Existing backend, frontend, and ARM64 build jobs remain independent. This does not configure GitHub branch protection: maintainers must make these checks required to prevent merging when they fail. A PR can still be opened through interfaces that bypass local commands.

Exceptions require an exact rule/path, a meaningful reason, and an existing accepted ADR. No wildcard suppression or inline ignore directive is supported. Policy changes and exceptions remain reviewable code; validation is not tamper-proof against someone deliberately changing the validator itself.

Record a local ignored report with source fingerprint, check results, and missing coverage. `--verify-report` rejects missing, failing, or stale reports before a PR is opened. Reports never include environment values or credentials. No command publishes, merges, provisions production, or installs hooks automatically.

## Limits

The tool enforces explicit organization/dependency/style rules, not arbitrary semantic purpose. It cannot prove that brewing logic belongs in a particular domain capability, establish hardware correctness, detect every secret or business invariant, or replace visual review and deployment tests. M1 and later feature PRs still cite requirements, UI/AC IDs, ADRs, and actual verification outcomes.
