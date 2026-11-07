"""Create local development credentials without printing or overwriting them."""

import os
from pathlib import Path
import secrets
import stat


def create_secrets(directory: Path) -> None:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or stat.S_IMODE(directory.stat().st_mode) != 0o700:
        raise ValueError("Secret directory must be a real directory with mode 0700")
    for name in ("admin-password", "migrator-password", "app-password"):
        path = directory / name
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or not path.read_bytes().strip():
                raise ValueError("Existing secret must be a nonempty regular file") from None
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(secrets.token_hex(32) + "\n")
            # Compose file secrets are bind mounts; their UID/mode aren't remapped.
            # Parent stays 0700; an assigned mount is readable by container UID 10001.
            os.fchmod(output.fileno(), 0o444)


if __name__ == "__main__":
    create_secrets(Path(__file__).resolve().parents[2] / ".secrets")
    print("Development password files are ready in .secrets/; existing files were preserved.")
