"""Règles d'autorisation métier liées aux rôles des collaborateurs."""

from models import Client, Employee

MANAGEMENT_ROLE = "GESTION"
COMMERCIAL_ROLE = "COMMERCIAL"
SUPPORT_ROLE = "SUPPORT"
APPLICATION_ROLES = frozenset(
    {MANAGEMENT_ROLE, COMMERCIAL_ROLE, SUPPORT_ROLE}
)


class AuthorizationError(PermissionError):
    """Levée lorsqu'un acteur ne possède pas la permission demandée."""


def has_role(employee: Employee | None, role_name: str) -> bool:
    """Indique si un collaborateur est associé au rôle demandé."""
    if employee is None or not isinstance(role_name, str):
        return False

    return employee.role is not None and employee.role.name == role_name


def is_authenticated(employee: Employee | None) -> bool:
    """Indique si l'objet correspond à un collaborateur de l'application."""
    if employee is None or employee.role is None:
        return False

    return employee.role.name in APPLICATION_ROLES


def can_manage_employees(actor: Employee | None) -> bool:
    """Indique si l'acteur peut créer, modifier ou supprimer un collaborateur."""
    return has_role(actor, MANAGEMENT_ROLE)


def can_manage_contracts(actor: Employee | None) -> bool:
    """Indique si l'acteur peut créer et modifier les contrats."""
    return has_role(actor, MANAGEMENT_ROLE)


def can_create_clients(actor: Employee | None) -> bool:
    """Indique si l'acteur peut créer un client et en devenir responsable."""
    return has_role(actor, COMMERCIAL_ROLE)


def can_update_client(actor: Employee | None, client: Client) -> bool:
    """Indique si le commercial est responsable du client à modifier."""
    if not has_role(actor, COMMERCIAL_ROLE):
        return False

    if client.commercial is actor:
        return True

    actor_id = getattr(actor, "id", None)
    commercial_id = getattr(client, "commercial_id", None)
    return (
        actor_id is not None
        and commercial_id is not None
        and actor_id == commercial_id
    )


def can_create_event(actor: Employee | None, contract: object) -> bool:
    """Indique si le commercial gère le client lié au contrat."""
    client = getattr(contract, "client", None)
    return client is not None and can_update_client(actor, client)


def can_assign_event_support(actor: Employee | None) -> bool:
    """Indique si l'acteur peut affecter le support d'un événement."""
    return has_role(actor, MANAGEMENT_ROLE)


def can_update_event(actor: Employee | None, event: object) -> bool:
    """Indique si l'acteur est le support affecté à l'événement."""
    if not has_role(actor, SUPPORT_ROLE):
        return False

    support = getattr(event, "support", None)
    if support is actor:
        return True

    actor_id = getattr(actor, "id", None)
    support_id = getattr(event, "support_id", None)
    return (
        actor_id is not None
        and support_id is not None
        and actor_id == support_id
    )
