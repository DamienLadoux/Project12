"""Opérations métier protégées sur les événements."""

from datetime import datetime

from sqlalchemy.orm import Session

from models import Contract, Employee, Event
from services.authorization import (
    SUPPORT_ROLE,
    AuthorizationError,
    can_assign_event_support,
    can_create_event,
    can_update_event,
    has_role,
)
from services.validators import optional_text, required_text

_UNSET = object()


class UnsignedContractError(ValueError):
    """Levée lorsqu'un événement cible un contrat non signé."""


class InvalidSupportError(ValueError):
    """Levée lorsque le collaborateur choisi n'appartient pas au support."""


def _validated_period(
    start_date: object,
    end_date: object,
) -> tuple[datetime, datetime]:
    """Valide les dates et leur ordre chronologique."""
    if not isinstance(start_date, datetime):
        raise ValueError("La date de début est invalide.")
    if not isinstance(end_date, datetime):
        raise ValueError("La date de fin est invalide.")
    if end_date < start_date:
        raise ValueError(
            "La date de fin ne peut pas précéder la date de début."
        )

    return start_date, end_date


def _validated_attendees(attendees: object) -> int:
    """Valide un nombre entier et positif ou nul de participants."""
    if (
        isinstance(attendees, bool)
        or not isinstance(attendees, int)
        or attendees < 0
    ):
        raise ValueError(
            "Le nombre de participants doit être un entier positif ou nul."
        )

    return attendees


def create_event(
    session: Session,
    actor: Employee | None,
    contract: Contract,
    name: str,
    start_date: datetime,
    end_date: datetime,
    location: str,
    attendees: int,
    *,
    notes: str | None = None,
) -> Event:
    """Crée un événement pour un contrat signé du commercial."""
    if not can_create_event(actor, contract):
        raise AuthorizationError(
            "Seul le commercial responsable du client peut créer "
            "cet événement."
        )
    if not contract.is_signed:
        raise UnsignedContractError(
            "Un événement exige un contrat signé."
        )

    normalized_name = required_text(
        name,
        "Le nom de l'événement est obligatoire.",
    )
    normalized_location = required_text(
        location,
        "Le lieu de l'événement est obligatoire.",
    )
    normalized_start, normalized_end = _validated_period(
        start_date,
        end_date,
    )
    normalized_attendees = _validated_attendees(attendees)
    normalized_notes = optional_text(notes)

    event = Event(
        contract=contract,
        name=normalized_name,
        start_date=normalized_start,
        end_date=normalized_end,
        location=normalized_location,
        attendees=normalized_attendees,
        notes=normalized_notes,
    )
    session.add(event)
    session.flush()

    return event


def assign_event_support(
    session: Session,
    actor: Employee | None,
    event: Event,
    support: Employee | None,
) -> Event:
    """Affecte ou retire un support, sur décision de la gestion."""
    if not can_assign_event_support(actor):
        raise AuthorizationError(
            "Seul le département gestion peut affecter le support."
        )
    if support is not None and not has_role(support, SUPPORT_ROLE):
        raise InvalidSupportError(
            "Le collaborateur affecté doit appartenir au support."
        )

    event.support = support
    session.flush()
    return event


def update_event(
    session: Session,
    actor: Employee | None,
    event: Event,
    *,
    contract: Contract | object = _UNSET,
    name: str | object = _UNSET,
    start_date: datetime | object = _UNSET,
    end_date: datetime | object = _UNSET,
    location: str | object = _UNSET,
    attendees: int | object = _UNSET,
    notes: str | None | object = _UNSET,
) -> Event:
    """Modifie un événement affecté au support connecté."""
    if not can_update_event(actor, event):
        raise AuthorizationError(
            "Seul le support affecté peut modifier cet événement."
        )

    values = (
        contract,
        name,
        start_date,
        end_date,
        location,
        attendees,
        notes,
    )
    if all(value is _UNSET for value in values):
        raise ValueError("Au moins une donnée doit être fournie.")

    changes: dict[str, object] = {}
    if name is not _UNSET:
        changes["name"] = required_text(
            name,
            "Le nom de l'événement est obligatoire.",
        )
    if location is not _UNSET:
        changes["location"] = required_text(
            location,
            "Le lieu de l'événement est obligatoire.",
        )

    candidate_start = event.start_date if start_date is _UNSET else start_date
    candidate_end = event.end_date if end_date is _UNSET else end_date
    normalized_start, normalized_end = _validated_period(
        candidate_start,
        candidate_end,
    )
    if start_date is not _UNSET:
        changes["start_date"] = normalized_start
    if end_date is not _UNSET:
        changes["end_date"] = normalized_end
    if attendees is not _UNSET:
        changes["attendees"] = _validated_attendees(attendees)
    if notes is not _UNSET:
        changes["notes"] = optional_text(notes)
    if contract is not _UNSET:
        if not isinstance(contract, Contract):
            raise ValueError(
                "Le contrat associé à l'événement est invalide."
            )
        if not contract.is_signed:
            raise UnsignedContractError(
                "Un événement exige un contrat signé."
            )
        changes["contract"] = contract

    for field_name, value in changes.items():
        setattr(event, field_name, value)

    session.flush()
    return event
