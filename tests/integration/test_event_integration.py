
"""Tests d'intégration des événements."""

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Client, Contract, Employee, Event, Role

load_dotenv()


@pytest.fixture
def db_session():
    """Fournit une session dont les modifications seront annulées."""
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


def create_test_contract(session):
    """Crée les données nécessaires à un contrat de test."""
    suffix = uuid4().hex

    role = Role(name=f"EVT_{suffix[:20]}")
    session.add(role)
    session.flush()

    employee = Employee(
        employee_number=f"E{suffix[:19]}",
        full_name="Commercial de test",
        email=f"{suffix}@example.test",
        password_hash="hash_de_test_non_utilisable",
        role=role,
    )
    session.add(employee)
    session.flush()

    client = Client(
        full_name="Client de test",
        email=f"client-{suffix}@example.test",
        commercial=employee,
    )
    session.add(client)
    session.flush()

    contract = Contract(
        client=client,
        total_amount=Decimal("1000.00"),
        remaining_amount=Decimal("1000.00"),
    )
    session.add(contract)
    session.flush()

    return contract


def test_event_is_saved_without_support(db_session):
    """Un événement peut exister sans support affecté."""
    contract = create_test_contract(db_session)

    event = Event(
        name="Événement de test",
        contract_id=contract.id,
        start_date=datetime(2027, 5, 10, 9, 0, tzinfo=timezone.utc),
        end_date=datetime(2027, 5, 10, 18, 0, tzinfo=timezone.utc),
        location="Paris",
        attendees=50,
    )
    db_session.add(event)
    db_session.flush()

    assert event.id is not None
    assert event.contract_id == contract.id
    assert event.support_id is None
    assert event in contract.events


def test_event_rejects_end_date_before_start_date(db_session):
    """PostgreSQL refuse une date de fin antérieure au début."""
    contract = create_test_contract(db_session)

    event = Event(
        name="Événement aux dates invalides",
        contract_id=contract.id,
        start_date=datetime(2027, 5, 11, 18, 0, tzinfo=timezone.utc),
        end_date=datetime(2027, 5, 11, 9, 0, tzinfo=timezone.utc),
        location="Paris",
        attendees=50,
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(event)
            db_session.flush()


def test_event_rejects_negative_attendees(db_session):
    """PostgreSQL refuse un nombre de participants négatif."""
    contract = create_test_contract(db_session)

    event = Event(
        name="Événement aux participants invalides",
        contract_id=contract.id,
        start_date=datetime(2027, 5, 10, 9, 0, tzinfo=timezone.utc),
        end_date=datetime(2027, 5, 10, 18, 0, tzinfo=timezone.utc),
        location="Paris",
        attendees=-1,
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(event)
            db_session.flush()
