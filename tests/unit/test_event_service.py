"""Tests unitaires du service de gestion des événements."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from models import Client, Contract, Employee, Event, Role
from services.authorization import AuthorizationError
from services.event_service import (
    InvalidSupportError,
    UnsignedContractError,
    assign_event_support,
    create_event,
    update_event,
)

START = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=8)


def employee_with_role(role_name: str, number: str = "EMP-001") -> Employee:
    """Construit un collaborateur utilisable comme actor ou cible."""
    return Employee(
        employee_number=number,
        full_name="Collaborateur test",
        email=f"{number.lower()}@example.test",
        password_hash="argon_hash",
        role=Role(name=role_name),
    )


def signed_contract_for(commercial: Employee) -> Contract:
    """Construit un contrat signé appartenant au commercial."""
    client = Client(
        full_name="Client test",
        email="client@example.test",
        commercial=commercial,
    )
    return Contract(client=client, is_signed=True)


def event_for(support: Employee | None = None) -> Event:
    """Construit un événement valide affecté au support fourni."""
    return Event(
        name="Événement test",
        start_date=START,
        end_date=END,
        location="Paris",
        attendees=100,
        support=support,
    )


def test_commercial_creates_event_for_own_signed_contract():
    """Le commercial responsable peut créer l'événement sans support."""
    session = MagicMock()
    commercial = employee_with_role("COMMERCIAL")
    contract = signed_contract_for(commercial)

    event = create_event(
        session,
        commercial,
        contract,
        " Gala annuel ",
        START,
        END,
        " Paris ",
        150,
        notes=" Prévoir un accueil ",
    )

    assert event.contract is contract
    assert event.name == "Gala annuel"
    assert event.location == "Paris"
    assert event.attendees == 150
    assert event.notes == "Prévoir un accueil"
    assert event.support is None
    session.add.assert_called_once_with(event)
    session.flush.assert_called_once()


def test_commercial_cannot_create_event_for_other_client():
    """Un commercial ne crée pas d'événement pour un autre portefeuille."""
    session = MagicMock()
    owner = employee_with_role("COMMERCIAL", "EMP-001")
    other = employee_with_role("COMMERCIAL", "EMP-002")

    with pytest.raises(AuthorizationError):
        create_event(
            session,
            other,
            signed_contract_for(owner),
            "Gala",
            START,
            END,
            "Paris",
            100,
        )

    session.add.assert_not_called()


def test_event_requires_signed_contract():
    """Le contrat du commercial doit être signé avant la création."""
    session = MagicMock()
    commercial = employee_with_role("COMMERCIAL")
    contract = signed_contract_for(commercial)
    contract.is_signed = False

    with pytest.raises(UnsignedContractError):
        create_event(
            session,
            commercial,
            contract,
            "Gala",
            START,
            END,
            "Paris",
            100,
        )

    session.add.assert_not_called()


def test_create_event_rejects_end_before_start():
    """Une période incohérente est refusée avant l'ajout en session."""
    session = MagicMock()
    commercial = employee_with_role("COMMERCIAL")

    with pytest.raises(ValueError):
        create_event(
            session,
            commercial,
            signed_contract_for(commercial),
            "Gala",
            END,
            START,
            "Paris",
            100,
        )

    session.add.assert_not_called()


def test_management_assigns_support_to_event():
    """L'acteur gestion peut affecter un collaborateur support."""
    session = MagicMock()
    management = employee_with_role("GESTION")
    support = employee_with_role("SUPPORT", "EMP-002")
    event = event_for()

    assigned_event = assign_event_support(
        session,
        management,
        event,
        support,
    )

    assert assigned_event is event
    assert event.support is support
    session.flush.assert_called_once()


def test_assign_event_rejects_non_support_employee():
    """Un commercial ne peut pas être affecté comme support."""
    session = MagicMock()
    event = event_for()

    with pytest.raises(InvalidSupportError):
        assign_event_support(
            session,
            employee_with_role("GESTION"),
            event,
            employee_with_role("COMMERCIAL", "EMP-002"),
        )

    assert event.support is None
    session.flush.assert_not_called()


def test_assigned_support_updates_event():
    """Le support affecté peut modifier tous les champs de l'événement."""
    session = MagicMock()
    support = employee_with_role("SUPPORT")
    event = event_for(support)
    new_contract = signed_contract_for(
        employee_with_role("COMMERCIAL", "EMP-002")
    )
    new_end = END + timedelta(hours=2)

    updated_event = update_event(
        session,
        support,
        event,
        contract=new_contract,
        name=" Nouveau nom ",
        end_date=new_end,
        attendees=120,
        notes=None,
    )

    assert updated_event is event
    assert event.contract is new_contract
    assert event.name == "Nouveau nom"
    assert event.end_date == new_end
    assert event.attendees == 120
    assert event.notes is None
    session.flush.assert_called_once()


def test_unassigned_support_cannot_update_event():
    """Un autre membre du support ne peut pas modifier l'événement."""
    session = MagicMock()
    assigned_support = employee_with_role("SUPPORT", "EMP-001")
    other_support = employee_with_role("SUPPORT", "EMP-002")
    event = event_for(assigned_support)

    with pytest.raises(AuthorizationError):
        update_event(session, other_support, event, name="Interdit")

    assert event.name == "Événement test"
    session.flush.assert_not_called()


def test_update_event_validates_before_mutation():
    """Une période invalide ne laisse aucune modification partielle."""
    session = MagicMock()
    support = employee_with_role("SUPPORT")
    event = event_for(support)

    with pytest.raises(ValueError, match="précéder"):
        update_event(
            session,
            support,
            event,
            name="Nom non appliqué",
            start_date=END + timedelta(hours=1),
        )

    assert event.name == "Événement test"
    assert event.start_date == START
    session.flush.assert_not_called()
