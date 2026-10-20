
"""Création des tables définies par les modèles SQLAlchemy."""

import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine

from models import Base


def main():
    """Crée les tables manquantes dans la base configurée."""
    load_dotenv()

    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
    )

    engine = create_engine(database_url)

    try:
        Base.metadata.create_all(engine)
        print("Création du schéma terminée.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
