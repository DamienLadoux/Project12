"""Tests unitaires du service de gestion des clients."""

from datetime import date

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from models import Employee, Role
from services.authorization import AuthorizationError
from services.client_service import create_client, update_client


def commercial_actor():
    """Construit un commercial minimal pour les tests."""
    return Employee(
        employee_number="EMP-001",
        full_name="Alice Martin",
        email="alice.martin@example.test",
        password_hash="argon_hash",
        role=Role(name="COMMERCIAL"),
    )


def test_commercial_creates_client_and_becomes_responsible():
    """Le client créé est automatiquement associé au commercial connecté."""
    session = MagicMock()
    actor = commercial_actor()

    client = create_client(
        session,
        actor,
        " Client de test ",
        " CLIENT@EXAMPLE.TEST ",
        phone=" 01 02 03 04 05 ",
        company_name=" Entreprise test ",
    )

    assert client.full_name == "Client de test"
    assert client.email == "client@example.test"
    assert client.phone == "01 02 03 04 05"
    assert client.company_name == "Entreprise test"
    assert client.commercial is actor
    session.add.assert_called_once_with(client)
    session.flush.assert_called_once()


def test_non_commercial_cannot_create_client():
    """La gestion ne peut pas créer un client à la place d'un commercial."""
    session = MagicMock()
    management = SimpleNamespace(role=SimpleNamespace(name="GESTION"))

    with pytest.raises(AuthorizationError):
        create_client(
            session,
            management,
            "Client de test",
            "client@example.test",
        )

    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_responsible_commercial_can_update_client():
    """Le commercial responsable peut actualiser toutes les données du client."""
    session = MagicMock()
    actor = commercial_actor()
    client = create_client(
        session,
        actor,
        "Client initial",
        "initial@example.test",
        phone="01 01 01 01 01",
        company_name="Entreprise initiale",
    )
    session.reset_mock()

    updated_client = update_client(
        session,
        actor,
        client,
        full_name=" Client actualisé ",
        email=" UPDATED@EXAMPLE.TEST ",
        phone=" 02 02 02 02 02 ",
        company_name=" Nouvelle entreprise ",
        last_contact_at=date(2026, 10, 21),
    )

    assert updated_client is client
    assert client.full_name == "Client actualisé"
    assert client.email == "updated@example.test"
    assert client.phone == "02 02 02 02 02"
    assert client.company_name == "Nouvelle entreprise"
    assert client.last_contact_at == date(2026, 10, 21)
    session.flush.assert_called_once()


def test_update_client_can_clear_optional_fields():
    """Une valeur vide ou None permet d'effacer les champs facultatifs."""
    session = MagicMock()
    actor = commercial_actor()
    client = create_client(
        session,
        actor,
        "Client test",
        "client@example.test",
        phone="01 01 01 01 01",
        company_name="Entreprise",
    )
    session.reset_mock()

    update_client(
        session,
        actor,
        client,
        phone=" ",
        company_name=None,
    )

    assert client.phone is None
    assert client.company_name is None
    session.flush.assert_called_once()


def test_other_commercial_cannot_update_client():
    """Un commercial ne peut pas modifier le portefeuille d'un collègue."""
    session = MagicMock()
    owner = commercial_actor()
    client = create_client(
        session,
        owner,
        "Client test",
        "client@example.test",
    )
    other_commercial = Employee(
        employee_number="EMP-002",
        full_name="Bob Martin",
        email="bob.martin@example.test",
        password_hash="argon_hash",
        role=Role(name="COMMERCIAL"),
    )
    session.reset_mock()

    with pytest.raises(AuthorizationError):
        update_client(
            session,
            other_commercial,
            client,
            full_name="Modification interdite",
        )

    assert client.full_name == "Client test"
    session.flush.assert_not_called()


def test_update_client_validates_everything_before_mutation():
    """Une erreur de validation ne laisse aucune modification partielle."""
    session = MagicMock()
    actor = commercial_actor()
    client = create_client(
        session,
        actor,
        "Client initial",
        "initial@example.test",
    )
    session.reset_mock()

    with pytest.raises(ValueError, match="invalide"):
        update_client(
            session,
            actor,
            client,
            full_name="Nouveau nom",
            email="adresse-invalide",
        )

    assert client.full_name == "Client initial"
    assert client.email == "initial@example.test"
    session.flush.assert_not_called()
