"""Opérations métier protégées sur les clients."""

from datetime import date

from sqlalchemy.orm import Session

from models import Client, Employee
from services.authorization import (
    AuthorizationError,
    can_create_clients,
    can_update_client,
)
from services.validators import normalize_email, optional_text, required_text

_UNSET = object()


def create_client(
    session: Session,
    actor: Employee | None,
    full_name: str,
    email: str,
    *,
    phone: str | None = None,
    company_name: str | None = None,
) -> Client:
    """Crée un client et l'associe automatiquement au commercial connecté."""
    if not can_create_clients(actor):
        raise AuthorizationError(
            "Seul un commercial peut créer un client."
        )

    client = Client(
        full_name=required_text(full_name, "Le nom complet est obligatoire."),
        email=normalize_email(email),
        phone=optional_text(phone),
        company_name=optional_text(company_name),
        commercial=actor,
    )
    session.add(client)
    session.flush()

    return client


def update_client(
    session: Session,
    actor: Employee | None,
    client: Client,
    *,
    full_name: str | object = _UNSET,
    email: str | object = _UNSET,
    phone: str | None | object = _UNSET,
    company_name: str | None | object = _UNSET,
    last_contact_at: date | None | object = _UNSET,
) -> Client:
    """Met à jour un client appartenant au commercial connecté.

    Les valeurs sont toutes validées avant de modifier l'objet, afin qu'une
    saisie invalide ne laisse pas le client partiellement modifié en mémoire.
    """
    if not can_update_client(actor, client):
        raise AuthorizationError(
            "Seul le commercial responsable peut modifier ce client."
        )

    changes = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "company_name": company_name,
        "last_contact_at": last_contact_at,
    }
    if all(value is _UNSET for value in changes.values()):
        raise ValueError("Au moins une donnée doit être fournie.")

    normalized_changes: dict[str, object] = {}
    if full_name is not _UNSET:
        normalized_changes["full_name"] = required_text(
            full_name,
            "Le nom complet est obligatoire.",
        )
    if email is not _UNSET:
        normalized_changes["email"] = normalize_email(email)
    if phone is not _UNSET:
        normalized_changes["phone"] = optional_text(phone)
    if company_name is not _UNSET:
        normalized_changes["company_name"] = optional_text(company_name)
    if last_contact_at is not _UNSET:
        if last_contact_at is not None and not isinstance(last_contact_at, date):
            raise ValueError("La date du dernier contact est invalide.")
        normalized_changes["last_contact_at"] = last_contact_at

    for field_name, value in normalized_changes.items():
        setattr(client, field_name, value)

    session.flush()
    return client
