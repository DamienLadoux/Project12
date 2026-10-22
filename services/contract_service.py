"""Opérations métier protégées sur les contrats."""

from decimal import Decimal

from sqlalchemy.orm import Session

from models import Client, Contract, Employee
from services.authorization import (
    AuthorizationError,
    can_manage_contracts,
    can_update_contract,
)
from services.validators import nonnegative_decimal

_UNSET = object()


def _validated_amounts(
    total_amount: object,
    remaining_amount: object,
) -> tuple[Decimal, Decimal]:
    """Valide la cohérence des deux montants d'un contrat."""
    normalized_total = nonnegative_decimal(total_amount, "Le montant total")
    normalized_remaining = nonnegative_decimal(
        remaining_amount,
        "Le montant restant",
    )
    if normalized_remaining > normalized_total:
        raise ValueError(
            "Le montant restant ne peut pas dépasser le montant total."
        )

    return normalized_total, normalized_remaining


def create_contract(
    session: Session,
    actor: Employee | None,
    client: Client,
    total_amount: object,
    remaining_amount: object,
    *,
    is_signed: bool = False,
) -> Contract:
    """Crée un contrat pour un client, sous le contrôle de la gestion."""
    if not can_manage_contracts(actor):
        raise AuthorizationError(
            "Seul le département gestion peut créer un contrat."
        )
    if not isinstance(is_signed, bool):
        raise ValueError("Le statut de signature doit être un booléen.")

    normalized_total, normalized_remaining = _validated_amounts(
        total_amount,
        remaining_amount,
    )
    contract = Contract(
        client=client,
        total_amount=normalized_total,
        remaining_amount=normalized_remaining,
        is_signed=is_signed,
    )
    session.add(contract)
    session.flush()

    return contract


def update_contract(
    session: Session,
    actor: Employee | None,
    contract: Contract,
    *,
    client: Client | object = _UNSET,
    total_amount: object = _UNSET,
    remaining_amount: object = _UNSET,
    is_signed: bool | object = _UNSET,
) -> Contract:
    """Modifie les informations financières ou la signature d'un contrat."""
    if all(
        value is _UNSET
        for value in (client, total_amount, remaining_amount, is_signed)
    ):
        raise ValueError("Au moins une donnée doit être fournie.")
    if client is not _UNSET and not isinstance(client, Client):
        raise ValueError("Le client associé au contrat est invalide.")

    target_client = None if client is _UNSET else client
    if not can_update_contract(actor, contract, target_client):
        raise AuthorizationError(
            "La modification est réservée à la gestion ou au commercial "
            "responsable du client."
        )

    candidate_total = (
        contract.total_amount if total_amount is _UNSET else total_amount
    )
    candidate_remaining = (
        contract.remaining_amount
        if remaining_amount is _UNSET
        else remaining_amount
    )
    normalized_total, normalized_remaining = _validated_amounts(
        candidate_total,
        candidate_remaining,
    )
    if is_signed is not _UNSET and not isinstance(is_signed, bool):
        raise ValueError("Le statut de signature doit être un booléen.")

    contract.total_amount = normalized_total
    contract.remaining_amount = normalized_remaining
    if client is not _UNSET:
        contract.client = client
    if is_signed is not _UNSET:
        contract.is_signed = is_signed

    session.flush()
    return contract
