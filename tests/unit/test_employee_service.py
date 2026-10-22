"""Tests unitaires du service de gestion des collaborateurs."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from models import Client, Employee, Event, Role
from services.employee_service import (
    AuthorizationError,
    EmployeeInUseError,
    UnknownRoleError,
    create_employee,
    delete_employee,
    update_employee,
)


def management_actor():
    """Construit un acteur du département gestion pour les tests."""
    return SimpleNamespace(role=SimpleNamespace(name="GESTION"))


@patch("services.employee_service.hash_password", return_value="argon_hash")
def test_management_can_create_employee_with_hashed_password(
    mock_hash_password,
):
    """La création associe le rôle trouvé et stocke uniquement le hachage."""
    role = Role(name="SUPPORT")
    session = MagicMock()
    session.scalar.return_value = role

    employee = create_employee(
        session=session,
        actor=management_actor(),
        employee_number=" EMP-001 ",
        full_name=" Alice Martin ",
        email=" ALICE.MARTIN@EXAMPLE.TEST ",
        password="MotDePasseTest!2026",
        role_name="SUPPORT",
    )

    assert employee.employee_number == "EMP-001"
    assert employee.full_name == "Alice Martin"
    assert employee.email == "alice.martin@example.test"
    assert employee.password_hash == "argon_hash"
    assert employee.role is role
    mock_hash_password.assert_called_once_with("MotDePasseTest!2026")
    session.add.assert_called_once_with(employee)
    session.flush.assert_called_once()


@patch("services.employee_service.hash_password")
def test_non_management_cannot_create_employee(mock_hash_password):
    """Un commercial ne peut pas créer de compte collaborateur."""
    session = MagicMock()
    commercial = SimpleNamespace(
        role=SimpleNamespace(name="COMMERCIAL")
    )

    with pytest.raises(AuthorizationError):
        create_employee(
            session,
            commercial,
            "EMP-001",
            "Alice Martin",
            "alice.martin@example.test",
            "MotDePasseTest!2026",
            "SUPPORT",
        )

    session.scalar.assert_not_called()
    session.add.assert_not_called()
    mock_hash_password.assert_not_called()


@patch("services.employee_service.hash_password")
def test_create_employee_rejects_unknown_role(mock_hash_password):
    """Le rôle doit exister avant que le mot de passe soit haché."""
    session = MagicMock()
    session.scalar.return_value = None

    with pytest.raises(UnknownRoleError):
        create_employee(
            session,
            management_actor(),
            "EMP-001",
            "Alice Martin",
            "alice.martin@example.test",
            "MotDePasseTest!2026",
            "INCONNU",
        )

    session.add.assert_not_called()
    mock_hash_password.assert_not_called()


@patch("services.employee_service.hash_password", return_value="new_argon_hash")
def test_management_can_update_employee_data_and_role(mock_hash_password):
    """La gestion peut modifier les champs autorisés d'un collaborateur."""
    old_role = Role(name="COMMERCIAL")
    new_role = Role(name="SUPPORT")
    employee = Employee(
        employee_number="EMP-001",
        full_name="Alice Martin",
        email="alice.martin@example.test",
        password_hash="old_argon_hash",
        role=old_role,
    )
    session = MagicMock()
    session.scalar.return_value = new_role

    updated_employee = update_employee(
        session,
        management_actor(),
        employee,
        employee_number=" EMP-014 ",
        full_name="Alice Dupont",
        email="ALICE.DUPONT@EXAMPLE.TEST",
        password="NouveauMotDePasse!2026",
        role_name="SUPPORT",
    )

    assert updated_employee is employee
    assert employee.employee_number == "EMP-014"
    assert employee.full_name == "Alice Dupont"
    assert employee.email == "alice.dupont@example.test"
    assert employee.password_hash == "new_argon_hash"
    assert employee.role is new_role
    mock_hash_password.assert_called_once_with("NouveauMotDePasse!2026")
    session.flush.assert_called_once()


def test_non_management_cannot_update_employee():
    """Un support ne peut pas modifier un compte collaborateur."""
    session = MagicMock()
    employee = MagicMock()
    support = SimpleNamespace(role=SimpleNamespace(name="SUPPORT"))

    with pytest.raises(AuthorizationError):
        update_employee(
            session,
            support,
            employee,
            full_name="Alice Dupont",
        )

    session.flush.assert_not_called()


def employee_without_responsibilities():
    """Construit un collaborateur sans client ni événement associé."""
    return Employee(
        employee_number="EMP-001",
        full_name="Alice Martin",
        email="alice.martin@example.test",
        password_hash="argon_hash",
        role=Role(name="SUPPORT"),
    )


def test_management_can_delete_employee_without_responsibilities():
    """La gestion peut supprimer un collaborateur non référencé."""
    session = MagicMock()
    employee = employee_without_responsibilities()

    delete_employee(session, management_actor(), employee)

    session.delete.assert_called_once_with(employee)
    session.flush.assert_called_once()


def test_delete_employee_rejects_commercial_responsible_for_client():
    """Un commercial responsable d'un client doit être réaffecté d'abord."""
    session = MagicMock()
    employee = employee_without_responsibilities()
    employee.clients.append(
        Client(full_name="Client test", email="client@example.test")
    )

    with pytest.raises(EmployeeInUseError):
        delete_employee(session, management_actor(), employee)

    session.delete.assert_not_called()
    session.flush.assert_not_called()


def test_delete_employee_rejects_support_responsible_for_event():
    """Un support responsable d'un événement doit être réaffecté d'abord."""
    session = MagicMock()
    employee = employee_without_responsibilities()
    employee.supported_events.append(Event())

    with pytest.raises(EmployeeInUseError):
        delete_employee(session, management_actor(), employee)

    session.delete.assert_not_called()
    session.flush.assert_not_called()


def test_non_management_cannot_delete_employee():
    """Un commercial ne peut pas supprimer un compte collaborateur."""
    session = MagicMock()
    commercial = SimpleNamespace(
        role=SimpleNamespace(name="COMMERCIAL")
    )

    with pytest.raises(AuthorizationError):
        delete_employee(
            session,
            commercial,
            employee_without_responsibilities(),
        )

    session.delete.assert_not_called()
    session.flush.assert_not_called()
