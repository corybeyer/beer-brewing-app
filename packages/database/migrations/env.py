"""Explicit Alembic entrypoint; URLs never go through config interpolation."""

from alembic import context
from sqlalchemy import create_engine, pool

from brewery_config import database_url


def run_migrations() -> None:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(connection=supplied_connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
        return
    url = database_url()
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=None, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=None)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
