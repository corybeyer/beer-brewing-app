"""Environment configuration for PostgreSQL adapters."""

import os
from pathlib import Path

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def web_assets_directory() -> Path | None:
    """Opt into serving a complete frontend build; never fall back to source."""
    value = os.environ.get("WEB_ASSETS_DIRECTORY")
    if value is None:
        return None
    directory = Path(value)
    if (not value or not directory.is_absolute() or not (directory / "index.html").is_file()
            or not (directory / "assets").is_dir()):
        raise ValueError("WEB_ASSETS_DIRECTORY must name a complete absolute frontend build directory")
    return directory


def read_password_file(path: str) -> str:
    try:
        password = Path(path).read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError):
        raise ValueError("Database password file is unreadable") from None
    if not password or "\n" in password or "\r" in password or "\x00" in password:
        raise ValueError("Database password file must contain one nonempty password")
    return password


def database_url(value: str | None = None) -> URL:
    """Require PostgreSQL and select Psycopg without logging credentials."""
    raw = value if value is not None else os.environ.get("DATABASE_URL", "")
    try:
        url = make_url(raw)
        if url.drivername not in ("postgresql", "postgresql+psycopg"):
            raise ValueError
        if not url.database:
            raise ValueError
    except (ArgumentError, ValueError):
        raise ValueError("DATABASE_URL must name a PostgreSQL database") from None
    if value is None and (path := os.environ.get("DATABASE_PASSWORD_FILE")):
        if url.password is not None:
            raise ValueError("Configure the database password in either URL or file, not both")
        url = url.set(password=read_password_file(path))
    return url.set(drivername="postgresql+psycopg")
