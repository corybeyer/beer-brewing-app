"""Run the local pre-PR checks and record a source-bound validation report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

if __package__:
    from .validation.repository import source_files
else:
    from validation.repository import source_files


def report_error(report, fingerprint, head, require_database=False):
    if not isinstance(report, dict) or report.get('passed') is not True:
        return 'The previous pre-PR run did not pass.'
    if report.get('fingerprint') != fingerprint or report.get('head') != head:
        return 'The pre-PR report is stale: source or base commit changed. Run the command again.'
    if require_database and report.get('incomplete'):
        return 'The report lacks required PostgreSQL integration/authentication coverage.'
    return None


def database_coverage(value):
    if not value:
        return ['PostgreSQL integration tests were not run; CI PostgreSQL checks remain required.']
    try:
        url = urlsplit(value)
        if not url.hostname or url.hostname.startswith('/') or parse_qs(url.query).get('host', [''])[0].startswith('/'):
            return ['TCP password-authentication coverage was skipped for a Unix-socket test database.']
    except ValueError:
        return ['Test database configuration could not be classified; check integration results.']
    return []


def write_report(root, report):
    directory = root / '.validation'
    if directory.is_symlink():
        raise ValueError('Validation report directory must not be a symlink.')
    directory.mkdir(mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=directory, encoding='utf-8', delete=False) as output:
        json.dump(report, output, indent=2)
        output.write('\n')
        temporary = Path(output.name)
    temporary.replace(directory / 'pre-pr.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-report', action='store_true', help='Verify that the last passing report still matches this source')
    parser.add_argument('--require-database', action='store_true', help='Require disposable TCP TEST_DATABASE_URL and integration coverage')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    _, fingerprint = source_files(root)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if args.verify_report:
        try:
            report = json.loads((root / '.validation/pre-pr.json').read_text())
        except (OSError, ValueError):
            print('No readable pre-PR report. Run python3 scripts/pre_pr.py first.', file=sys.stderr)
            return 1
        error = report_error(report, fingerprint, head, args.require_database)
        if error:
            print(error, file=sys.stderr)
            return 1
        print('PASS: the local pre-PR report matches this source and base commit.')
        for gap in report.get('incomplete', []):
            print('NOT VERIFIED: ' + gap)
        return 0

    incomplete = database_coverage(os.environ.get('TEST_DATABASE_URL'))
    report = {'version': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'head': head,
              'fingerprint': fingerprint, 'passed': False, 'incomplete': incomplete, 'checks': []}
    if args.require_database and incomplete:
        write_report(root, report)
        print('A disposable TCP TEST_DATABASE_URL is required. No credential value is printed.', file=sys.stderr)
        return 2
    node, npm = shutil.which('node'), shutil.which('npm')
    python = root / '.venv/bin/python'
    if not python.exists():
        python = Path(sys.executable)
    if not node or not npm:
        write_report(root, report)
        print('Install Node 24 and run npm ci; install Python backend dependencies before pre-PR checks.', file=sys.stderr)
        return 2
    steps = [
        ('Repository ownership, boundaries, visuals, contracts, secrets, and documentation', [sys.executable, 'scripts/validate_repository.py']),
        ('Frontend validator regression fixtures', [node, '--test', 'tests/unit/frontend_validator.test.mjs']),
        ('Python unit, contract, API, and available PostgreSQL integration tests', [str(python), '-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        ('Frontend type check and production build', [npm, 'run', 'build']),
        ('Browser, shared-component, accessibility, and file-access checks', [npm, 'test']),
    ]
    try:
        for name, command in steps:
            print('\nRUN: ' + name, flush=True)
            result = subprocess.run(command, cwd=root)
            report['checks'].append({'name': name, 'passed': result.returncode == 0})
            if result.returncode:
                print('FAIL: pre-PR checks stopped; fix the failed check and rerun.', file=sys.stderr)
                write_report(root, report)
                return 1
        current_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        if source_files(root)[1] != fingerprint or current_head != head:
            print('Source/base changed while checks ran; rerun before opening the PR.', file=sys.stderr)
            write_report(root, report)
            return 1
        report['passed'] = True
        write_report(root, report)
    except KeyboardInterrupt:
        write_report(root, report)
        print('\nPre-PR run interrupted; the report is not passing.', file=sys.stderr)
        return 130
    print('\nPASS: local pre-PR checks. Report: .validation/pre-pr.json')
    for gap in incomplete:
        print('NOT VERIFIED: ' + gap)
    print('CI still validates ARM64 images and its independent PostgreSQL environment.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
