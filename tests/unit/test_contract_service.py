"""Tests unitaires du service de gestion des contrats."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from models import Client, Contract
from services.authorization import AuthorizationError
from services.contract_service import create_contract, update_contract


def actor_with_role(role_name: str):
    """Construit l'acteur transmis au service après authentification."""
    return SimpleNamespace(role=SimpleNamespace(name=role_name))


def test_management_actor_can_create_contract():
    """L'acteur gestion peut créer un contrat aux montants cohérents."""
    session = MagicMock()
    client = Client(full_name="Client test", email="client@example.test")

    contract = create_contract(
        session,
        actor_with_role("GESTION"),
        client,
        "1500.50",
        1000,
        is_signed=False,
    )

    assert contract.client is client
    assert contract.total_amount == Decimal("1500.50")
    assert contract.remaining_amount == Decimal("1000")
    assert contract.is_signed is False
    session.add.assert_called_once_with(contract)
    session.flush.assert_called_once()


@pytest.mark.parametrize("role_name", ["COMMERCIAL", "SUPPORT"])
def test_non_management_actor_cannot_create_contract(role_name):
    """L'objet actor porte le rôle utilisé pour refuser l'opération."""
    session = MagicMock()
    client = Client(full_name="Client test", email="client@example.test")

    with pytest.raises(AuthorizationError):
        create_contract(
            session,
            actor_with_role(role_name),
            client,
            1000,
            500,
        )

    session.add.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.parametrize(
    ("total_amount", "remaining_amount"),
    [
        (1000, 1001),
        ("montant invalide", 0),
    ],
)
def test_create_contract_rejects_invalid_amounts(
    total_amount,
    remaining_amount,
):
    """Les montants invalides sont refusés avant la persistance."""
    session = MagicMock()
    client = Client(full_name="Client test", email="client@example.test")

    with pytest.raises(ValueError):
        create_contract(
            session,
            actor_with_role("GESTION"),
            client,
            total_amount,
            remaining_amount,
        )

    session.add.assert_not_called()
    session.flush.assert_not_called()


def test_management_actor_can_update_contract():
    """La gestion peut modifier tous les champs, dont le client."""
    session = MagicMock()
    new_client = Client(
        full_name="Nouveau client",
        email="nouveau@example.test",
    )
    contract = Contract(
        total_amount=Decimal("1000"),
        remaining_amount=Decimal("1000"),
        is_signed=False,
    )

    updated_contract = update_contract(
        session,
        actor_with_role("GESTION"),
        contract,
        client=new_client,
        total_amount="1200",
        remaining_amount="400",
        is_signed=True,
    )

    assert updated_contract is contract
    assert contract.client is new_client
    assert contract.total_amount == Decimal("1200")
    assert contract.remaining_amount == Decimal("400")
    assert contract.is_signed is True
    session.flush.assert_called_once()


def test_update_contract_validates_before_mutation():
    """Un ensemble incohérent ne modifie aucun champ du contrat."""
    session = MagicMock()
    contract = Contract(
        total_amount=Decimal("1000"),
        remaining_amount=Decimal("500"),
        is_signed=False,
    )

    with pytest.raises(ValueError, match="dépasser"):
        update_contract(
            session,
            actor_with_role("GESTION"),
            contract,
            total_amount="400",
            is_signed=True,
        )

    assert contract.total_amount == Decimal("1000")
    assert contract.remaining_amount == Decimal("500")
    assert contract.is_signed is False
    session.flush.assert_not_called()
