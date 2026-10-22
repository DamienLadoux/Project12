"""Intégration des principaux parcours de création et de mise à jour."""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import create_database_engine
from models import Client, Contract, Employee, Event, Role
from security.passwords import verify_password
from services.contract_service import create_contract, update_contract
from services.employee_service import create_employee, update_employee
from services.event_service import (
    assign_event_support,
    create_event,
    update_event,
)


load_dotenv()


@pytest.fixture
def db_session():
    """Isole chaque test dans une transaction PostgreSQL annulée à la fin."""
    if os.getenv("DB_NAME") != "epic_events":
        pytest.skip("Ce test est réservé à la base de développement.")

    engine = create_database_engine()
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


def _role(session: Session, name: str) -> Role:
    """Récupère ou initialise un rôle dans la transaction de test."""
    role = session.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        session.add(role)
        session.flush()
    return role


def _employee(session: Session, role_name: str, label: str) -> Employee:
    """Crée un acteur persistant avec des identifiants uniques."""
    suffix = uuid4().hex
    employee = Employee(
        employee_number=f"{label}{suffix[:15]}",
        full_name=f"{label} de test",
        email=f"{label.lower()}-{suffix}@example.test",
        password_hash="hachage-de-test",
        role=_role(session, role_name),
    )
    session.add(employee)
    session.flush()
    return employee


def _client(
    session: Session,
    commercial: Employee,
    label: str,
) -> Client:
    """Crée un client persistant rattaché au commercial fourni."""
    suffix = uuid4().hex
    client = Client(
        full_name=f"Client {label}",
        email=f"client-{label.lower()}-{suffix}@example.test",
        commercial=commercial,
    )
    session.add(client)
    session.flush()
    return client


def test_employee_creation_and_full_update_are_persisted(db_session):
    """La gestion crée puis modifie l'identité, le mot de passe et le rôle."""
    manager = _employee(db_session, "GESTION", "MGR")
    _role(db_session, "COMMERCIAL")
    _role(db_session, "SUPPORT")
    suffix = uuid4().hex

    employee = create_employee(
        db_session,
        manager,
        f"NEW{suffix[:15]}",
        "Collaborateur initial",
        f"initial-{suffix}@example.test",
        "MotDePasseInitial!2026",
        "COMMERCIAL",
    )
    employee_id = employee.id

    update_employee(
        db_session,
        manager,
        employee,
        employee_number=f"UPD{suffix[:15]}",
        full_name="Collaborateur modifié",
        email=f"modifie-{suffix}@example.test",
        password="NouveauMotDePasse!2026",
        role_name="SUPPORT",
    )

    db_session.expire_all()
    stored_employee = db_session.get(Employee, employee_id)

    assert stored_employee is not None
    assert stored_employee.employee_number == f"UPD{suffix[:15]}"
    assert stored_employee.full_name == "Collaborateur modifié"
    assert stored_employee.email == f"modifie-{suffix}@example.test"
    assert stored_employee.role.name == "SUPPORT"
    assert verify_password(
        "NouveauMotDePasse!2026",
        stored_employee.password_hash,
    )


def test_contract_creation_and_full_update_are_persisted(db_session):
    """La gestion modifie tous les champs du contrat."""
    manager = _employee(db_session, "GESTION", "MGR")
    commercial = _employee(db_session, "COMMERCIAL", "COM")
    first_client = _client(db_session, commercial, "initial")
    second_client = _client(db_session, commercial, "final")

    contract = create_contract(
        db_session,
        manager,
        first_client,
        "1000.00",
        "1000.00",
    )
    contract_id = contract.id

    update_contract(
        db_session,
        manager,
        contract,
        client=second_client,
        total_amount="1500.00",
        remaining_amount="250.00",
        is_signed=True,
    )

    db_session.expire_all()
    stored_contract = db_session.get(Contract, contract_id)

    assert stored_contract is not None
    assert stored_contract.client_id == second_client.id
    assert stored_contract.total_amount == Decimal("1500.00")
    assert stored_contract.remaining_amount == Decimal("250.00")
    assert stored_contract.is_signed is True


def test_event_creation_and_full_update_are_persisted(db_session):
    """Les acteurs autorisés créent, affectent puis modifient l'événement."""
    manager = _employee(db_session, "GESTION", "MGR")
    commercial = _employee(db_session, "COMMERCIAL", "COM")
    support = _employee(db_session, "SUPPORT", "SUP")
    client = _client(db_session, commercial, "evenement")
    first_contract = Contract(
        client=client,
        total_amount=Decimal("1000.00"),
        remaining_amount=Decimal("500.00"),
        is_signed=True,
    )
    second_contract = Contract(
        client=client,
        total_amount=Decimal("2000.00"),
        remaining_amount=Decimal("1000.00"),
        is_signed=True,
    )
    db_session.add_all([first_contract, second_contract])
    db_session.flush()

    start = datetime(2027, 5, 10, 9, 0, tzinfo=timezone.utc)
    event = create_event(
        db_session,
        commercial,
        first_contract,
        "Événement initial",
        start,
        start + timedelta(hours=8),
        "Paris",
        50,
        notes="Note initiale",
    )
    event_id = event.id
    assign_event_support(db_session, manager, event, support)

    new_start = start + timedelta(days=1)
    new_end = new_start + timedelta(hours=10)
    update_event(
        db_session,
        support,
        event,
        contract=second_contract,
        name="Événement modifié",
        start_date=new_start,
        end_date=new_end,
        location="Lyon",
        attendees=75,
        notes="Note modifiée",
    )

    db_session.expire_all()
    stored_event = db_session.get(Event, event_id)

    assert stored_event is not None
    assert stored_event.contract_id == second_contract.id
    assert stored_event.support_id == support.id
    assert stored_event.name == "Événement modifié"
    assert stored_event.start_date == new_start
    assert stored_event.end_date == new_end
    assert stored_event.location == "Lyon"
    assert stored_event.attendees == 75
    assert stored_event.notes == "Note modifiée"
