
"""Test d'intégration de la contrainte d'unicité des rôles."""

import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Role

load_dotenv()

@pytest.fixture
def db_session():
    """Fournit une session transactionnelle pour le test."""
    if os.getenv("DB_NAME") != "epic_events":
        pytest.skip("Ce test nécessite la base epic_events.")

    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
    )

    engine = create_engine(database_url)

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_duplicate_role_name_is_rejected(db_session):
    """PostgreSQL refuse deux rôles portant le même nom."""
    first_role = Role(name="TDD_TEST_ROLE")
    db_session.add(first_role)
    db_session.flush()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(Role(name="TDD_TEST_ROLE"))
            db_session.flush()
