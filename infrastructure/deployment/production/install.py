"""Install reviewed production operations once; never reads a sudo password."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile

if __package__:
    from .rollout import DATA_VOLUME, Deployment, REPOSITORY, atomic_write
else:
    from rollout import DATA_VOLUME, Deployment, REPOSITORY, atomic_write


def private_directory(path):
    if path.is_symlink():
        raise ValueError('Installation directories must not be symlinks')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o077:
        raise ValueError('Installation directory must be privately owned by the administrator')


def refuse_unclaimed_volume(deployment):
    if not deployment.root.exists():
        volumes = deployment.command('volume', 'ls', '--format', '{{.Name}}').decode().splitlines()
        if DATA_VOLUME in volumes:
            raise ValueError('Production volume already exists without this installation; administrator review is required')


def install_files(host, binaries, units, initial_images):
    """Stage source-owned operations and retain exact legacy files before switching."""
    host, binaries, units = Path(host), Path(binaries), Path(units)
    runtime = host / 'runtime'
    if runtime.exists() or runtime.is_symlink():
        raise ValueError('Production runtime is already staged; use the installed deploy/rollback commands')
    for path in (host, binaries, units):
        if path.is_symlink() or path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o022:
            raise ValueError('Installation parent must be administrator-owned and not writable by others')
    legacy = [host / 'compose.yaml', host / '.env', binaries / 'brewery-deploy']
    for path in legacy:
        if not path.is_file() or path.is_symlink() or path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o022:
            raise ValueError('Legacy deployment files must be regular administrator-owned files')
    for path in (binaries / 'brewery-backup', binaries / 'brewery-rollback-legacy',
                 units / 'brewery-backup.service', units / 'brewery-backup.timer'):
        if path.exists() or path.is_symlink():
            raise ValueError('Refusing to replace an unrelated administrator command or unit')
    original = (binaries / 'brewery-deploy').read_bytes()
    source = Path(__file__).resolve().parent
    stage = Path(tempfile.mkdtemp(prefix='.runtime-install-', dir=host))
    try:
        for src, name in [(host / 'compose.yaml', 'legacy-compose.yaml'),
                          (host / '.env', 'legacy.env'), (binaries / 'brewery-deploy', 'legacy-deploy'),
                          (source / 'compose.yaml', 'compose.yaml'), (source / 'rollout.py', 'rollout.py')]:
            if src.is_symlink() or not src.is_file():
                raise ValueError('Installation sources must be regular files')
            shutil.copyfile(src, stage / name)
            (stage / name).chmod(0o600)
        (stage / 'legacy-deploy').chmod(0o700)
        private_directory(stage / 'secrets')
        for name in ('admin-password', 'migrator-password', 'app-password'):
            path = stage / 'secrets' / name
            with path.open('x') as output:
                os.chmod(path, 0o444)
                output.write(secrets.token_hex(32) + '\n')
        atomic_write(stage / 'installation.json', json.dumps({'format': 1,
                     'legacy_deployer_sha256': hashlib.sha256(original).hexdigest()}))
        stage.rename(runtime)
        Deployment(runtime, host / 'unused-backup-path').write_environment(*initial_images)
        # Root compose and .env remain exact legacy copies in their original locations.
        # Only the sudoers-allowed executable is switched, after all backups exist.
        launcher = f'#!/bin/sh\nexec /usr/bin/python3 -I "{runtime / "rollout.py"}"'
        for name, operation in [('brewery-deploy', 'deploy'), ('brewery-backup', 'backup'),
                                ('brewery-rollback-legacy', 'rollback-legacy')]:
            destination = binaries / name
            atomic_write(destination, launcher + f' {operation} "$@"\n', mode=0o700)
        atomic_write(units / 'brewery-backup.service',
                     '[Unit]\nDescription=Verified brewery PostgreSQL backup\nAfter=docker.service\n'
                     '[Service]\nType=oneshot\nUser=root\nUMask=0077\n'
                     f'ExecStart={binaries / "brewery-backup"}\n')
        atomic_write(units / 'brewery-backup.timer',
                     '[Unit]\nDescription=Daily verified brewery backup\n[Timer]\nOnCalendar=daily\n'
                     'Persistent=true\nRandomizedDelaySec=15m\n[Install]\nWantedBy=timers.target\n')
        return runtime
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True, help='Validated and published main commit to deploy')
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.commit):
        raise SystemExit('A full lowercase Git commit SHA is required.')
    if os.geteuid() != 0:
        raise SystemExit('Administrator access is required. Run this reviewed installer with sudo; do not send a password to Codex.')
    os.umask(0o077)
    host = Path('/opt/beer-brewing-app')
    # Inspect current configuration locally; never print its contents or secrets.
    current = json.loads(subprocess.check_output(['/usr/bin/docker', 'compose',
                         '--env-file', str(host / '.env'), '-f', str(host / 'compose.yaml'),
                         'config', '--format', 'json'], env={'PATH': '/usr/bin:/bin', 'HOME': '/root'}, timeout=30))
    brewery = current.get('services', {}).get('brewery', {})
    if (set(current.get('services', {})) != {'brewery'} or brewery.get('volumes')
            or brewery.get('environment') or brewery.get('container_name')
            or brewery.get('command') or brewery.get('entrypoint')
            or set(brewery) - {'image', 'ports', 'restart', 'networks', 'command', 'entrypoint'}
            or current.get('name') != 'beer-brewing-app'
            or not re.fullmatch(re.escape(REPOSITORY) + r'@sha256:[0-9a-f]{64}', brewery.get('image', ''))
            or any(port.get('target') != 8080 or port.get('published') != '8080'
                   or port.get('protocol', 'tcp') != 'tcp'
                   or port.get('host_ip', '0.0.0.0') not in ('0.0.0.0', '') for port in brewery.get('ports', []))
            or not brewery.get('ports')):
        raise SystemExit('Current host configuration differs from the reviewed smoke deployment; stop for administrator review.')
    # Resolve/validate both images before changing any host files.
    deployment = Deployment(host / 'runtime', '/var/backups/beer-brewing-app')
    application, operator = deployment.image(args.commit, 'app'), deployment.image(args.commit, 'operator')
    refuse_unclaimed_volume(deployment)
    private_directory(Path('/var/backups/beer-brewing-app'))
    if deployment.root.exists():
        private_directory(deployment.root)
        private_directory(deployment.root / 'secrets')
        source = Path(__file__).resolve().parent
        if (not (deployment.root / 'installation.json').is_file()
                or json.loads((deployment.root / 'installation.json').read_text()).get('format') != 1
                or any((deployment.root / name).is_symlink()
                       or (deployment.root / name).read_bytes() != (source / name).read_bytes()
                       for name in ('compose.yaml', 'rollout.py'))):
            raise SystemExit('Staged operations differ from the reviewed package; administrator review is required.')
        # Resume a failed first deployment/timer setup without replacing credentials.
    else:
        install_files(host, '/usr/local/sbin', '/etc/systemd/system', (brewery['image'], operator))
    with deployment.locked():
        deployment.deploy_images(application, operator)
    subprocess.run(['/usr/bin/systemctl', 'daemon-reload'], check=True)
    subprocess.run(['/usr/bin/systemctl', 'enable', '--now', 'brewery-backup.timer'], check=True)
    print('Production UI/API installed; daily verified backups enabled. Legacy rollback files retained.')


if __name__ == '__main__':
    main()
