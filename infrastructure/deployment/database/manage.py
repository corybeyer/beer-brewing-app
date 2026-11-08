"""Provision limited roles and run explicit migrations with metadata read grants."""

import argparse
import os

from alembic import command
from alembic.config import Config
import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from brewery_config import database_url, read_password_file


def provision(connection, migrator: str, application: str, migrator_password: str, application_password: str) -> None:
    if not migrator or not application or migrator == application:
        raise ValueError("Migration and application roles must have distinct names")
    with connection.transaction():
        database, admin = connection.execute("SELECT current_database(), current_user").fetchone()
        if admin in (migrator, application):
            raise ValueError("Provisioning requires a separate administrator")
        for role, password in ((migrator, migrator_password), (application, application_password)):
            row = connection.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolcanlogin, rolinherit "
                "FROM pg_roles WHERE rolname = %s", (role,),
            ).fetchone()
            memberships = connection.execute(
                "SELECT 1 FROM pg_auth_members WHERE member = (SELECT oid FROM pg_roles WHERE rolname = %s)",
                (role,),
            ).fetchone()
            if row is not None:
                if any(row[:5]) or not row[5] or row[6] or memberships:
                    raise ValueError("Existing database role has unexpected privileges or memberships")
                continue
            verifier = connection.pgconn.encrypt_password(
                password.encode("utf-8"), role.encode("utf-8"), b"scram-sha-256",
            ).decode("utf-8")
            connection.execute(sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}"
            ).format(sql.Identifier(role), sql.Literal(verifier)))

        connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
            sql.Identifier(database), sql.Identifier(migrator), sql.Identifier(application)))
        connection.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        connection.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(migrator)))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(application)))
        connection.execute(sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
        ).format(sql.Identifier(migrator)))


def migrate(url, application: str, config_path: str = "alembic.ini") -> None:
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.begin() as connection:
            config = Config(config_path)
            config.attributes["connection"] = connection
            config.attributes["application_role"] = application
            command.upgrade(config, "head")
            role = connection.dialect.identifier_preparer.quote_identifier(application)
            connection.exec_driver_sql(f"REVOKE ALL ON TABLE public.alembic_version FROM {role}")
            connection.exec_driver_sql(f"GRANT SELECT ON TABLE public.alembic_version TO {role}")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("provision", "migrate"))
    arguments = parser.parse_args()
    application = os.environ.get("APPLICATION_ROLE", "brewery_app")
    if arguments.operation == "migrate":
        migrate(database_url(), application)
    else:
        url = database_url().set(drivername="postgresql")
        with psycopg.connect(url.render_as_string(hide_password=False)) as connection:
            provision(
                connection,
                os.environ.get("MIGRATION_ROLE", "brewery_migrator"),
                application,
                read_password_file(os.environ["MIGRATOR_PASSWORD_FILE"]),
                read_password_file(os.environ["APPLICATION_PASSWORD_FILE"]),
            )
    print("Database operation completed.")


if __name__ == "__main__":
    try:
        main()
    except (psycopg.Error, SQLAlchemyError):
        raise SystemExit("Database operation failed; verify permissions and local credentials.") from None
