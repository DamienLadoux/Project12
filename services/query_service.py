"""Consultation et filtrage des données du CRM."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import Client, Contract, Employee, Event
from services.authorization import (
    AuthorizationError,
    COMMERCIAL_ROLE,
    SUPPORT_ROLE,
    can_manage_employees,
    has_role,
    is_authenticated,
)


def _require_authenticated(actor: Employee | None) -> Employee:
    """Retourne l'acteur authentifié ou refuse l'accès aux données."""
    if not is_authenticated(actor):
        raise AuthorizationError(
            "L'authentification est requise pour consulter les données."
        )

    return actor


def _actor_id(actor: Employee) -> int:
    """Retourne l'identifiant nécessaire aux filtres de propriété."""
    if actor.id is None:
        raise ValueError(
            "Le collaborateur doit être enregistré avant ce filtrage."
        )

    return actor.id


def list_employees(
    session: Session,
    actor: Employee | None,
) -> list[Employee]:
    """Liste les collaborateurs pour le seul département gestion."""
    authenticated_actor = _require_authenticated(actor)
    if not can_manage_employees(authenticated_actor):
        raise AuthorizationError(
            "Seul le département gestion peut consulter les collaborateurs."
        )

    statement = (
        select(Employee)
        .options(selectinload(Employee.role))
        .order_by(Employee.id)
    )
    return list(session.scalars(statement).all())


def list_clients(
    session: Session,
    actor: Employee | None,
    *,
    mine_only: bool = False,
) -> list[Client]:
    """Liste les clients, avec un filtre sur le portefeuille commercial."""
    authenticated_actor = _require_authenticated(actor)
    statement = (
        select(Client)
        .options(selectinload(Client.commercial))
        .order_by(Client.id)
    )

    if mine_only:
        if not has_role(authenticated_actor, COMMERCIAL_ROLE):
            raise AuthorizationError(
                "Le filtre 'mes clients' est réservé aux commerciaux."
            )
        statement = statement.where(
            Client.commercial_id == _actor_id(authenticated_actor)
        )

    return list(session.scalars(statement).all())


def list_contracts(
    session: Session,
    actor: Employee | None,
    *,
    mine_only: bool = False,
    unsigned_only: bool = False,
    unpaid_only: bool = False,
) -> list[Contract]:
    """Liste les contrats et combine les filtres métier demandés."""
    authenticated_actor = _require_authenticated(actor)
    statement = (
        select(Contract)
        .options(
            selectinload(Contract.client).selectinload(Client.commercial)
        )
        .order_by(Contract.id)
    )

    if mine_only:
        if not has_role(authenticated_actor, COMMERCIAL_ROLE):
            raise AuthorizationError(
                "Le filtre 'mes contrats' est réservé aux commerciaux."
            )
        statement = statement.join(Contract.client).where(
            Client.commercial_id == _actor_id(authenticated_actor)
        )
    if unsigned_only:
        statement = statement.where(Contract.is_signed.is_(False))
    if unpaid_only:
        statement = statement.where(Contract.remaining_amount > 0)

    return list(session.scalars(statement).all())


def list_events(
    session: Session,
    actor: Employee | None,
    *,
    mine_only: bool = False,
    without_support_only: bool = False,
) -> list[Event]:
    """Liste les événements, affectés au support ou encore non affectés."""
    authenticated_actor = _require_authenticated(actor)
    statement = (
        select(Event)
        .options(
            selectinload(Event.contract)
            .selectinload(Contract.client)
            .selectinload(Client.commercial),
            selectinload(Event.support),
        )
        .order_by(Event.id)
    )

    if mine_only:
        if not has_role(authenticated_actor, SUPPORT_ROLE):
            raise AuthorizationError(
                "Le filtre 'mes événements' est réservé au support."
            )
        statement = statement.where(
            Event.support_id == _actor_id(authenticated_actor)
        )
    if without_support_only:
        statement = statement.where(Event.support_id.is_(None))

    return list(session.scalars(statement).all())
