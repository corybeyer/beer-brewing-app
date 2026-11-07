"""Git-aware, dependency-free Python side of the repository policy checker."""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

RULES = {
    'layout.owner', 'layout.source', 'layout.test', 'layout.contract', 'layout.migration',
    'layout.lock', 'layout.generated', 'security.file', 'security.content', 'security.ignore',
    'python.syntax', 'python.dependency', 'python.dynamic', 'python.configuration',
    'python.ddl', 'manifest.dependencies', 'manifest.exports', 'manifest.cycle',
    'migration.graph', 'migration.readiness', 'docs.link', 'syntax.json', 'tool.frontend',
    'js.syntax', 'js.dependency', 'js.private-import', 'js.undeclared', 'js.dynamic',
    'js.inline-style', 'js.literal', 'js.native-control', 'js.svg', 'js.transport', 'js.configuration',
    'css.syntax', 'css.feature', 'css.literal', 'css.token', 'css.import', 'css.breakpoint',
    'policy.exception',
}
CODE = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.css', '.sql'}
JS = {'.ts', '.tsx', '.js', '.jsx', '.mjs'}
GENERATED = {'node_modules', '__pycache__', '.venv', 'dist', 'test-results', 'playwright-report', '.validation'}


def finding(rule, path, message, line=1):
    return {'rule': rule, 'path': path, 'line': line, 'message': message}


def owner_of(path, policy):
    return next((name for name, item in policy['owners'].items()
                 if path == item['root'] or path.startswith(item['root'] + '/')), None)


def allowed(owner, dependency, policy):
    uses = policy['owners'][owner]['uses']
    return owner == dependency or '*' in uses or dependency in uses


def validate_policy(policy):
    if policy.get('version') != 1 or not isinstance(policy.get('owners'), dict):
        raise ValueError('Unsupported or incomplete repository policy.')
    roots = []
    for name, item in policy['owners'].items():
        if not all(key in item for key in ('root', 'uses', 'python', 'node')):
            raise ValueError('Every policy owner needs root, uses, python, and node rules.')
        root = item['root']
        if not root or root.startswith('/') or '..' in PurePosixPath(root).parts or any(c in root for c in '*?[]'):
            raise ValueError('Policy owner roots must be exact repository-relative paths.')
        if any(root == other or root.startswith(other + '/') or other.startswith(root + '/') for other in roots):
            raise ValueError('Policy owner roots must not overlap.')
        roots.append(root)
        if any(target not in policy['owners'] and target != '*' for target in item['uses']):
            raise ValueError('Policy dependency references an unknown owner.')
        if '*' in item['uses'] and name not in ('tests', 'scripts', 'infrastructure'):
            raise ValueError('Runtime owners cannot have wildcard dependencies.')
    for target in (*policy['python_modules'].values(), *policy['node_packages'].values()):
        if target not in policy['owners']:
            raise ValueError('Module registry references an unknown owner.')
    active, done = set(), set()
    def visit(name):
        if name in active:
            raise ValueError('Repository policy dependency graph contains a cycle.')
        if name in done:
            return
        active.add(name)
        for target in policy['owners'][name]['uses']:
            if target != '*':
                visit(target)
        active.remove(name)
        done.add(name)
    for name in policy['owners']:
        visit(name)


def source_files(root):
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=root, check=True, stdout=subprocess.PIPE)
    files = {}
    digest = hashlib.sha256()
    for name in sorted(set(result.stdout.decode().split('\0')) - {''}):
        path = root / name
        if not path.is_file():
            continue  # Removed paths are absent from the proposed snapshot.
        if path.is_symlink():
            raise ValueError(f'Source symlink needs explicit review: {name}')
        content = path.read_bytes()
        digest.update(name.encode() + b'\0' + hashlib.sha256(content).digest())
        try:
            files[name] = content.decode('utf-8')
        except UnicodeError:
            files[name] = None
    return files, digest.hexdigest()


def python_findings(path, content, policy):
    owner = owner_of(path, policy)
    try:
        tree = ast.parse(content)
    except SyntaxError as error:
        return [finding('python.syntax', path, 'Python source does not parse.', error.lineno or 1)]
    if owner not in policy['owners'] or owner in ('tests', 'scripts', 'infrastructure'):
        return []
    results = []
    known = policy['python_modules']
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or '') + '.' + item.name
    def canonical(name):
        first, dot, remainder = name.partition('.')
        return aliases.get(first, first) + (dot + remainder if dot else '')
    forbidden_stdlib = {'sqlite3', 'socket', 'http', 'urllib', 'subprocess'} if owner in ('domain', 'validation') else set()
    if owner == 'api':
        forbidden_stdlib |= {'sqlite3'}

    def dependency(module, line):
        top = module.split('.')[0]
        target = known.get(top)
        external = policy['owners'][owner]['python']
        if (target and not allowed(owner, target, policy)) or top in forbidden_stdlib or (
                not target and top not in sys.stdlib_module_names and '*' not in external and top not in external):
            results.append(finding('python.dependency', path,
                                   f'{owner} cannot import {top}; use the owning package interface.', line))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dependency(alias.name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if not node.level:
                dependency(node.module or '', node.lineno)
            else:
                package = next((module for module, target in known.items() if target == owner), None)
                root = policy['owners'][owner]['root']
                tail = path[len(root) + 1:].split('/')
                if package in tail:
                    parents = tail[tail.index(package):-1]
                    if node.level > len(parents):
                        results.append(finding('python.dependency', path, 'Relative import escapes its owning Python package.', node.lineno))
                    else:
                        dependency('.'.join(parents[:len(parents) - node.level + 1] + ((node.module or '').split('.') if node.module else [])), node.lineno)
        elif isinstance(node, ast.Call):
            name = canonical(ast.unparse(node.func))
            if name in ('__import__', 'importlib.import_module'):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    dependency(node.args[0].value, node.lineno)
                else:
                    results.append(finding('python.dynamic', path, 'Computed imports require an explicit policy exception.', node.lineno))
            if name in ('os.getenv', 'os.environ.get', 'os.environ.setdefault') and owner != 'config':
                results.append(finding('python.configuration', path, 'Read environment configuration through packages/config.', node.lineno))
        elif isinstance(node, ast.Subscript) and canonical(ast.unparse(node.value)) == 'os.environ' and owner != 'config':
            results.append(finding('python.configuration', path, 'Read environment configuration through packages/config.', node.lineno))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and owner not in ('database',):
            if re.match(r'\s*(CREATE|ALTER|DROP)\s+(TABLE|SCHEMA|DATABASE)\b', node.value, re.I):
                results.append(finding('python.ddl', path, 'Schema operations belong in database migrations or provisioning.', node.lineno))
    return results


def migration_findings(files):
    revisions, results = {}, []
    for path, content in files.items():
        if not path.startswith('packages/database/migrations/versions/') or not path.endswith('.py') or path.endswith('__init__.py'):
            continue
        values = {}
        try:
            for node in ast.parse(content or '').body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ('revision', 'down_revision'):
                            values[target.id] = ast.literal_eval(node.value)
        except (SyntaxError, ValueError, TypeError):
            results.append(finding('migration.graph', path, 'Migration revisions must be literal values.'))
            continue
        revision = values.get('revision')
        if not isinstance(revision, str) or not revision or 'down_revision' not in values or revision in revisions:
            results.append(finding('migration.graph', path, 'Migration revision is missing, invalid, or duplicated.'))
        else:
            previous = values['down_revision']
            parents = [] if previous is None else [previous] if isinstance(previous, str) else previous
            if not isinstance(parents, (tuple, list)) or not all(isinstance(p, str) for p in parents):
                results.append(finding('migration.graph', path, 'Invalid parent revision.'))
            else:
                revisions[revision] = (parents, path)
    seen, visiting = set(), set()
    def visit(revision):
        if revision in visiting:
            results.append(finding('migration.graph', revisions[revision][1], 'Migration graph contains a cycle.'))
            return
        if revision in seen:
            return
        visiting.add(revision)
        for parent in revisions[revision][0]:
            if parent not in revisions:
                results.append(finding('migration.graph', revisions[revision][1], 'Migration references an absent parent.'))
            else:
                visit(parent)
        visiting.remove(revision)
        seen.add(revision)
    for revision in revisions:
        visit(revision)
    if revisions:
        heads = set(revisions) - {p for parents, _ in revisions.values() for p in parents}
        if len(heads) != 1:
            results.append(finding('migration.graph', 'packages/database/migrations/versions', 'Expected one migration head; merge divergent revisions.'))
        path = 'packages/database/src/brewery_database/connection.py'
        for node in ast.walk(ast.parse(files.get(path) or '')):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCHEMA_REVISION' for t in node.targets):
                if not isinstance(node.value, ast.Constant) or node.value.value not in heads:
                    results.append(finding('migration.readiness', path, 'Readiness revision must match the migration head.', node.lineno))
    return results


def python_checks(files, policy):
    results = []
    for path, content in files.items():
        parts, suffix = PurePosixPath(path).parts, PurePosixPath(path).suffix
        owner = owner_of(path, policy)
        archived = path.startswith('docs/references/')
        if any(part in GENERATED or part.endswith('.egg-info') for part in parts):
            results.append(finding('layout.generated', path, 'Generated/dependency files must not enter Git.'))
            continue
        if '.secrets' in parts or (PurePosixPath(path).name.startswith('.env') and path != '.env.example') or suffix in ('.db', '.sqlite3', '.pem', '.key'):
            results.append(finding('security.file', path, 'Sensitive/runtime files must stay outside Git.'))
            continue
        if len(parts) == 1 and path not in policy['root_files'] or len(parts) > 1 and owner is None:
            results.append(finding('layout.owner', path, 'File has no approved owner; place it under a declared concern.'))
        if path.startswith(('apps/', 'packages/')) and owner is None:
            continue
        if archived:
            continue  # Archived go-bys are not executable application instructions.
        if suffix in CODE and owner in ('docs', 'github', 'agents'):
            results.append(finding('layout.source', path, 'Executable application code does not belong in documentation/configuration folders.'))
        if suffix in ('.tsx', '.jsx', '.css') and owner not in ('web', 'ui', 'design-system', 'tests'):
            results.append(finding('layout.source', path, 'Visual source belongs in web/UI/design-system or test fixtures.'))
        if suffix == '.py' and owner in ('web', 'ui', 'design-system'):
            results.append(finding('layout.source', path, 'Python runtime code belongs in its backend concern.'))
        name = PurePosixPath(path).name
        if (name.startswith('test_') or '.spec.' in name or '.test.' in name) and suffix in CODE and owner != 'tests':
            results.append(finding('layout.test', path, 'Tests belong under categorized tests/.'))
        if name.endswith('.schema.json') and not path.startswith(('packages/communications/contracts/', 'tests/fixtures/')):
            results.append(finding('layout.contract', path, 'Versioned communication schemas belong in communications/contracts.'))
        if ('migrations' in parts or suffix == '.sql') and not path.startswith(('packages/database/migrations/', 'infrastructure/deployment/database/', 'tests/fixtures/')):
            results.append(finding('layout.migration', path, 'Schema migrations/DDL belong to database or explicit provisioning.'))
        if name in ('package-lock.json', 'yarn.lock', 'pnpm-lock.yaml') and path != 'package-lock.json':
            results.append(finding('layout.lock', path, 'Use the single root npm workspace lock.'))
        if owner == 'tests' and len(parts) > 2 and parts[1] not in ('unit', 'integration', 'contract', 'e2e', 'fixtures'):
            results.append(finding('layout.test', path, 'Categorize tests as unit/integration/contract/e2e/fixtures.'))
        if content is None:
            continue
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b', content):
            results.append(finding('security.content', path, 'Potential private key or access token; remove it without copying its value into reports.'))
        if suffix == '.py':
            results.extend(python_findings(path, content, policy))
        if suffix == '.json':
            try:
                json.loads(content)
            except ValueError:
                results.append(finding('syntax.json', path, 'JSON does not parse.'))
        if suffix == '.md':
            for target in re.findall(r'\]\(([^)]+)\)', content):
                if re.match(r'^[a-zA-Z][a-zA-Z+.-]*:', target) or target.startswith('#'):
                    continue
                target = unquote(target.strip('<>').split('#', 1)[0])
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
                if target and resolved not in files and not any(f.startswith(resolved.rstrip('/') + '/') for f in files):
                    results.append(finding('docs.link', path, 'Local documentation target is missing: ' + target))
    results.extend(migration_findings(files))
    return results


def filter_exceptions(results, policy, files):
    exceptions, errors = set(), []
    for item in policy.get('exceptions', []):
        path, rule = item.get('path', ''), item.get('rule', '')
        adr = files.get(item.get('adr', '')) or ''
        nonwaivable = rule.startswith(('security.', 'syntax.')) or rule in ('layout.generated', 'policy.exception', 'tool.frontend', 'python.syntax', 'js.syntax', 'css.syntax')
        if rule not in RULES or nonwaivable or any(c in path for c in '*?[]') or path not in files or len(item.get('reason', '')) < 20 or not re.search(r'Status:\s*Accepted', adr):
            errors.append(finding('policy.exception', 'scripts/validation/policy.json', 'Exceptions require a known rule, exact existing path, meaningful reason, and accepted ADR.'))
        else:
            exceptions.add((rule, path))
    return [result for result in results if (result['rule'], result['path']) not in exceptions] + errors


def validate(root, frontend=True):
    files, fingerprint = source_files(root)
    policy = json.loads((root / 'scripts/validation/policy.json').read_text())
    validate_policy(policy)
    results = python_checks(files, policy)
    for sample in ('.secrets/check', '.env', '.env.local', 'node_modules/check', '.validation/check'):
        if subprocess.run(['git', 'check-ignore', '--no-index', '-q', sample], cwd=root).returncode:
            results.append(finding('security.ignore', '.gitignore', 'Missing Git exclusion for ' + sample))
    dockerignore = files.get('.dockerignore') or ''
    for pattern in ('.secrets', '.env', '.env.*', '**/node_modules', '.validation'):
        if pattern not in dockerignore.splitlines() or any(line.startswith('!') and ('.secrets' in line or '.env' in line or 'node_modules' in line or '.validation' in line) for line in dockerignore.splitlines()):
            results.append(finding('security.ignore', '.dockerignore', 'Preserve Docker exclusion for ' + pattern))
    if frontend:
        node = shutil.which('node')
        if not node:
            raise ValueError('Node 24 is required; install Node and run npm ci before validation.')
        payload = {'files': {p: c for p, c in files.items() if c is not None and (PurePosixPath(p).suffix in JS | {'.css'} or p.endswith('package.json')) and not p.startswith('docs/references/')}, 'policy': policy}
        process = subprocess.run([node, 'scripts/validation/frontend.mjs'], cwd=root,
                                 input=json.dumps(payload), text=True, capture_output=True)
        if process.returncode:
            raise ValueError('Frontend parser checks could not run. Run npm ci and check the validator dependencies.')
        results.extend(json.loads(process.stdout))
    results = filter_exceptions(results, policy, files)
    return {'passed': not results, 'files_checked': len(files), 'fingerprint': fingerprint,
            'findings': sorted(results, key=lambda f: (f['path'], f['line'], f['rule']))}
