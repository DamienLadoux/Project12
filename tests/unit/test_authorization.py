"""Tests unitaires des règles d'autorisation."""

from types import SimpleNamespace

import pytest

from services.authorization import (
    can_assign_event_support,
    can_create_clients,
    can_create_event,
    can_manage_contracts,
    can_manage_employees,
    can_update_client,
    can_update_event,
    has_role,
    is_authenticated,
)


def make_employee_with_role(role_name: str):
    """Construit un collaborateur minimal pour tester les permissions."""
    return SimpleNamespace(role=SimpleNamespace(name=role_name))


def test_has_role_uses_the_role_associated_with_employee():
    """Le rôle est lu depuis la relation Employee.role."""
    employee = make_employee_with_role("COMMERCIAL")

    assert has_role(employee, "COMMERCIAL")
    assert not has_role(employee, "GESTION")


@pytest.mark.parametrize("role_name", ["GESTION", "COMMERCIAL", "SUPPORT"])
def test_application_roles_are_authenticated(role_name):
    """Chaque rôle connu représente un collaborateur authentifié."""
    assert is_authenticated(make_employee_with_role(role_name))


def test_missing_or_unknown_role_is_not_authenticated():
    """L'absence d'acteur ou un rôle inconnu ne donne aucun accès."""
    assert not is_authenticated(None)
    assert not is_authenticated(make_employee_with_role("INCONNU"))


@pytest.mark.parametrize("role_name", ["COMMERCIAL", "SUPPORT"])
def test_only_management_can_manage_employees(role_name):
    """Les rôles commercial et support ne gèrent pas les collaborateurs."""
    employee = make_employee_with_role(role_name)

    assert not can_manage_employees(employee)


def test_management_can_manage_employees():
    """Le rôle gestion peut administrer les collaborateurs."""
    employee = make_employee_with_role("GESTION")

    assert can_manage_employees(employee)


def test_only_management_can_manage_contracts():
    """Les contrats sont administrés par le département gestion."""
    management = make_employee_with_role("GESTION")
    commercial = make_employee_with_role("COMMERCIAL")
    support = make_employee_with_role("SUPPORT")

    assert can_manage_contracts(management)
    assert not can_manage_contracts(commercial)
    assert not can_manage_contracts(support)
    assert not can_manage_contracts(None)


def test_unauthenticated_actor_cannot_manage_employees():
    """Une action protégée exige un collaborateur authentifié."""
    assert not can_manage_employees(None)


def test_only_commercial_can_create_clients():
    """La création d'un client appartient uniquement au département commercial."""
    commercial = make_employee_with_role("COMMERCIAL")
    management = make_employee_with_role("GESTION")
    support = make_employee_with_role("SUPPORT")

    assert can_create_clients(commercial)
    assert not can_create_clients(management)
    assert not can_create_clients(support)


def test_commercial_can_only_update_owned_client():
    """Un commercial ne peut modifier que les clients qui lui sont affectés."""
    commercial = make_employee_with_role("COMMERCIAL")
    other_commercial = make_employee_with_role("COMMERCIAL")
    owned_client = SimpleNamespace(
        commercial=commercial,
        commercial_id=None,
    )
    other_client = SimpleNamespace(
        commercial=other_commercial,
        commercial_id=None,
    )

    assert can_update_client(commercial, owned_client)
    assert not can_update_client(commercial, other_client)


@pytest.mark.parametrize("role_name", ["GESTION", "SUPPORT"])
def test_non_commercial_cannot_update_client(role_name):
    """Les autres départements ne modifient pas les fiches clients."""
    actor = make_employee_with_role(role_name)
    client = SimpleNamespace(commercial=actor, commercial_id=None)

    assert not can_update_client(actor, client)


def test_commercial_can_create_event_for_owned_client_contract():
    """La permission de création remonte du contrat vers le commercial."""
    commercial = make_employee_with_role("COMMERCIAL")
    client = SimpleNamespace(commercial=commercial, commercial_id=None)
    contract = SimpleNamespace(client=client)

    assert can_create_event(commercial, contract)
    assert not can_create_event(
        make_employee_with_role("COMMERCIAL"),
        contract,
    )


def test_only_management_can_assign_event_support():
    """L'affectation d'un support appartient au département gestion."""
    assert can_assign_event_support(make_employee_with_role("GESTION"))
    assert not can_assign_event_support(make_employee_with_role("SUPPORT"))


def test_only_assigned_support_can_update_event():
    """Le support doit être celui qui est affecté à l'événement."""
    support = make_employee_with_role("SUPPORT")
    other_support = make_employee_with_role("SUPPORT")
    event = SimpleNamespace(support=support, support_id=None)

    assert can_update_event(support, event)
    assert not can_update_event(other_support, event)
    assert not can_update_event(make_employee_with_role("GESTION"), event)
