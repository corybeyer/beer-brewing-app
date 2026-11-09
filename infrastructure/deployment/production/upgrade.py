"""Explicit administrator update of known installed operations; no deployment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

if __package__:
    from .rollout import Deployment, atomic_write
else:
    from rollout import Deployment, atomic_write


PREDECESSOR_SHA256 = 'b57b58d514554d870f8271d0a9d585b918f41cf2c965938ea5e1f358a1b8293d'
RECIPE_PREDECESSOR_SHA256 = '545c7bcf971327a054981c6bbdd6c228f5b048808d147d13f3a68bb1e04790f4'
COMPOSE_SHA256 = '55b973731a6e589d8369b5a2877f5edae54f5fdf5a7acd3bbdf1ca53c0e18fc6'


def owned(path, directory=False, private=True):
    if (path.is_symlink() or not (path.is_dir() if directory else path.is_file())
            or path.stat().st_uid != os.geteuid()
            or path.stat().st_mode & (0o077 if private else 0o022)):
        raise ValueError('Operations upgrade requires owned, regular, safely permissioned installation files.')


def verify_checkout(source, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('A full lowercase reviewed Git commit is required.')
    repository = source.parents[2]
    command = ['git', '-c', f'safe.directory={repository}']
    options = {'cwd': repository, 'env': {'PATH': '/usr/bin:/bin', 'HOME': '/root'},
               'stderr': subprocess.PIPE, 'text': True, 'timeout': 30}
    if subprocess.check_output([*command, 'rev-parse', 'HEAD'], **options).strip() != commit:
        raise ValueError('Checkout must match the exact reviewed commit.')
    if subprocess.check_output([*command, 'status', '--porcelain', '--untracked-files=normal'], **options).strip():
        raise ValueError('Checkout must be clean before installing reviewed operations.')


def upgrade_operations(host, binaries, source, commit):
    """Replace only known operations under the existing deployment/backup lock."""
    host, binaries, source = Path(host), Path(binaries), Path(source)
    runtime = host / 'runtime'
    owned(host, directory=True, private=False)
    owned(binaries, directory=True, private=False)
    owned(runtime, directory=True)
    owned(runtime / 'secrets', directory=True)
    for name in ('rollout.py', 'compose.yaml', 'installation.json', '.env', 'legacy.env', 'legacy-compose.yaml', 'legacy-deploy'):
        owned(runtime / name)
    owned(host / 'compose.yaml', private=False)
    owned(host / '.env')
    for name, operation in (('brewery-deploy', 'deploy'), ('brewery-backup', 'backup'),
                            ('brewery-rollback-legacy', 'rollback-legacy')):
        path = binaries / name
        owned(path, private=False)
        expected = f'#!/bin/sh\nexec /usr/bin/python3 -I "{runtime / "rollout.py"}" {operation} "$@"\n'
        if path.read_text() != expected or path.stat().st_mode & 0o777 != 0o700:
            raise ValueError('Installed launcher differs from the reviewed installation.')
    if set(path.name for path in (runtime / 'secrets').iterdir()) != {'admin-password', 'migrator-password', 'app-password'}:
        raise ValueError('Installed credentials differ from the reviewed installation.')
    for path in (runtime / 'secrets').iterdir():
        owned(path, private=False)  # Read-only mounts may have mode 0444 in a private parent.
    installation = json.loads((runtime / 'installation.json').read_text())
    if (installation.get('format') != 1
            or installation.get('legacy_deployer_sha256') != hashlib.sha256((runtime / 'legacy-deploy').read_bytes()).hexdigest()
            or (runtime / 'legacy-compose.yaml').read_bytes() != (host / 'compose.yaml').read_bytes()
            or (runtime / 'legacy.env').read_bytes() != (host / '.env').read_bytes()):
        raise ValueError('Retained legacy installation does not match its original files.')
    for name in ('rollout.py', 'compose.yaml'):
        if (source / name).is_symlink() or not (source / name).is_file():
            raise ValueError('Reviewed operations sources must be regular files.')
    replacement = (source / 'rollout.py').read_text()
    compile(replacement, 'reviewed-rollout.py', 'exec')
    target_hash = hashlib.sha256(replacement.encode()).hexdigest()
    if (hashlib.sha256((source / 'compose.yaml').read_bytes()).hexdigest() != COMPOSE_SHA256
            or (runtime / 'compose.yaml').read_bytes() != (source / 'compose.yaml').read_bytes()):
        raise ValueError('Compose changes require a separately reviewed installer.')
    deployment = Deployment(runtime, '/var/backups/beer-brewing-app')
    with deployment.locked():
        original = (runtime / 'rollout.py').read_text()
        original_hash = hashlib.sha256(original.encode()).hexdigest()
        if original_hash not in (PREDECESSOR_SHA256, RECIPE_PREDECESSOR_SHA256, target_hash):
            raise ValueError('Installed operations have an unknown predecessor; stop for administrator review.')
        history = runtime / 'operations-history'
        if not history.exists():
            history.mkdir(mode=0o700)
        owned(history, directory=True)
        retained = history / f'rollout-{original_hash}.py'
        if retained.exists() or retained.is_symlink():
            owned(retained)
            if retained.read_text() != original:
                raise ValueError('Retained operations history differs from installed source.')
        else:
            atomic_write(retained, original)
        receipt = runtime / 'operations.json'
        if receipt.exists() or receipt.is_symlink():
            owned(receipt)
        try:
            atomic_write(runtime / 'rollout.py', replacement)
            atomic_write(receipt, json.dumps({'format': 1, 'reviewed_commit': commit,
                                              'operations_sha256': target_hash}))
        except Exception:
            atomic_write(runtime / 'rollout.py', original)
            raise
    return target_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True, help='Exact clean, reviewed PR or main commit')
    arguments = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Administrator access is required; enter sudo authentication only in your terminal.')
    os.umask(0o077)
    source = Path(__file__).resolve().parent
    verify_checkout(source, arguments.commit)
    upgrade_operations('/opt/beer-brewing-app', '/usr/local/sbin', source, arguments.commit)
    print('Reviewed deployment/backup operations installed; images, database, credentials, and timer unchanged.')


if __name__ == '__main__':
    main()
