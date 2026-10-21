"""Configuration centralisée de la connexion PostgreSQL."""

import os

from sqlalchemy import URL, Engine, create_engine


def build_database_url() -> URL:
    """Construit l'URL SQLAlchemy depuis les variables d'environnement."""
    required_values = {
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
        "DB_NAME": os.getenv("DB_NAME"),
    }
    missing_values = [
        name for name, value in required_values.items() if not value
    ]
    if missing_values:
        raise ValueError(
            "Variables manquantes dans .env : " + ", ".join(missing_values)
        )

    return URL.create(
        drivername="postgresql+psycopg",
        username=required_values["DB_USER"],
        password=required_values["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=required_values["DB_NAME"],
    )


def create_database_engine() -> Engine:
    """Crée le moteur utilisé par l'application en ligne de commande."""
    return create_engine(build_database_url())
