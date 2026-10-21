
"""Tests d'intégration du modèle Client."""

import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, select
from sqlalchemy.orm import Session

from models import Client, Employee, Role

load_dotenv()


@pytest.fixture
def db_session():
    """Fournit une session isolée par une transaction annulée ensuite."""
    if os.getenv("DB_NAME") != "epic_events":
        pytest.skip("Ce test est réservé à la base de développement.")

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
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()


def test_client_is_linked_to_its_commercial(db_session):
    """Un client enregistré référence le bon collaborateur."""
    suffix = uuid4().hex
    role = Role(name=f"TC_{suffix[:20]}")
    db_session.add(role)
    db_session.flush()

    employee = Employee(
        employee_number=f"T{suffix[:19]}",
        full_name="Commercial de test",
        email=f"{suffix}@example.test",
        password_hash="hash_de_test_non_utilisable",
        role=role,
    )
    db_session.add(employee)
    db_session.flush()

    client = Client(
        full_name="Client de test",
        email=f"client-{suffix}@example.test",
        commercial=employee,
    )
    db_session.add(client)
    db_session.flush()

    client_id = client.id
    employee_id = employee.id

    db_session.expire_all()
    saved_client = db_session.scalar(
        select(Client).where(Client.id == client_id)
    )

    assert saved_client is not None
    assert saved_client.commercial_id == employee_id
    assert saved_client.commercial.id == employee_id
    assert saved_client in employee.clients
