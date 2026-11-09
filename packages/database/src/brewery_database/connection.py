"""Bounded PostgreSQL connections and schema readiness."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError


SCHEMA_REVISION = "0004_conversion_proposals"


def create_database_engine(url: URL) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
        hide_parameters=True,
    )


def database_is_ready(engine: Engine) -> bool:
    """An accessible database without the expected schema is not ready."""
    try:
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()
        return revisions == [SCHEMA_REVISION]
    except SQLAlchemyError:
        # Driver exceptions can contain hosts/usernames. Do not expose them.
        return False
