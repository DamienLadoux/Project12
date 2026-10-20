
"""Initialise la base PostgreSQL si elle n'existe pas."""

import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text


def main():
    """Crée la base de données si elle est absente."""
    load_dotenv()

    admin_db_name = os.getenv("ADMIN_DB_NAME")
    admin_db_user = os.getenv("ADMIN_DB_USER")
    admin_db_password = os.getenv("ADMIN_DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))

    required_values = {
        "ADMIN_DB_NAME": admin_db_name,
        "ADMIN_DB_USER": admin_db_user,
        "ADMIN_DB_PASSWORD": admin_db_password,
        "DB_NAME": db_name,
    }

    missing_values = [
        name for name, value in required_values.items() if not value
    ]

    if missing_values:
        raise ValueError(
            "Variables manquantes dans .env : "
            + ", ".join(missing_values)
        )

    if db_name == admin_db_name:
        raise ValueError(
            "La base cible doit être différente de la base administrative."
        )

    admin_url = URL.create(
        drivername="postgresql+psycopg",
        username=admin_db_user,
        password=admin_db_password,
        host=db_host,
        port=db_port,
        database=admin_db_name,
    )

    engine = create_engine(
        admin_url,
        isolation_level="AUTOCOMMIT",
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    "SELECT 1 FROM pg_database "
                    "WHERE datname = :db_name"
                ),
                {"db_name": db_name},
            )

            if result.scalar_one_or_none():
                print(f"La base '{db_name}' existe déjà.")
                return

            quoted_db_name = (
                connection.dialect.identifier_preparer.quote(db_name)
            )

            connection.exec_driver_sql(
                f"CREATE DATABASE {quoted_db_name}"
            )

            print(f"Base '{db_name}' créée avec succès.")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
