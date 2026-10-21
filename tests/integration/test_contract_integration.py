
"""Tests d'intégration des contrats."""

import os
from decimal import Decimal

import pytest
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Client, Contract, Employee, Role

load_dotenv()


@pytest.fixture
def db_session():
    """Ouvre une transaction annulée à la fin du test."""
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


def test_contract_rejects_remaining_amount_above_total(db_session):
    """Le montant restant ne peut pas dépasser le montant total."""
    role = Role(name="TEST_CONTRACT_ROLE")
    db_session.add(role)
    db_session.flush()

    employee = Employee(
        employee_number="TEST_CONTRACT_01",
        full_name="Commercial de test",
        email="commercial-contract-test@example.test",
        password_hash="hash_de_test_non_utilisable",
        role=role,
    )
    db_session.add(employee)
    db_session.flush()

    client = Client(
        full_name="Client de test",
        email="client-contract-test@example.test",
        commercial=employee,
    )
    db_session.add(client)
    db_session.flush()

    contract = Contract(
        client=client,
        total_amount=Decimal("1000.00"),
        remaining_amount=Decimal("1200.00"),
    )
    db_session.add(contract)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()
