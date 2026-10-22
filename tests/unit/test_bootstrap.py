"""Tests de l'amorçage sécurisé d'une base Epic Events vide."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import bootstrap
from models import Base, Employee, Role
from security.passwords import verify_password


@pytest.fixture
def empty_session():
    """Fournit une base SQLite vide pour tester l'amorçage localement."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_bootstrap_creates_roles_and_management_employee(empty_session):
    """Une base vide reçoit ses rôles et un gestionnaire authentifiable."""
    employee = bootstrap.create_initial_management_employee(
        empty_session,
        " EMP-001 ",
        " Alice Martin ",
        "ALICE@EXAMPLE.TEST",
        "MotDePasse!2026",
    )

    role_names = set(empty_session.scalars(select(Role.name)))
    assert role_names == {"GESTION", "COMMERCIAL", "SUPPORT"}
    assert employee.employee_number == "EMP-001"
    assert employee.full_name == "Alice Martin"
    assert employee.email == "alice@example.test"
    assert employee.role.name == "GESTION"
    assert verify_password("MotDePasse!2026", employee.password_hash)


def test_bootstrap_refuses_database_containing_employee(empty_session):
    """L'amorçage ne devient jamais une création de compte non autorisée."""
    bootstrap.create_initial_management_employee(
        empty_session,
        "EMP-001",
        "Alice Martin",
        "alice@example.test",
        "MotDePasse!2026",
    )

    with pytest.raises(ValueError, match="existe déjà"):
        bootstrap.create_initial_management_employee(
            empty_session,
            "EMP-002",
            "Bob Martin",
            "bob@example.test",
            "MotDePasse!2026",
        )


@patch("bootstrap.create_database_engine")
@patch("bootstrap.configure_monitoring")
@patch("bootstrap.load_dotenv")
def test_bootstrap_rejects_password_mismatch_before_database_access(
    mock_load_dotenv,
    mock_configure_monitoring,
    mock_create_engine,
):
    """Une confirmation incorrecte n'ouvre aucune connexion."""
    with (
        patch("builtins.input", side_effect=["EMP-001", "Alice", "a@b.c"]),
        patch("bootstrap.getpass.getpass", side_effect=["one", "two"]),
        pytest.raises(ValueError, match="ne correspondent pas"),
    ):
        bootstrap.main()

    mock_create_engine.assert_not_called()


def test_bootstrap_main_creates_account_and_audit_event():
    """Le parcours interactif valide la transaction avant l'audit Sentry."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with (
        patch("bootstrap.load_dotenv") as mock_load_dotenv,
        patch("bootstrap.configure_monitoring") as mock_monitoring,
        patch("bootstrap.create_database_engine", return_value=engine),
        patch(
            "builtins.input",
            side_effect=["EMP-001", "Alice Martin", "alice@example.test"],
        ),
        patch(
            "bootstrap.getpass.getpass",
            side_effect=["MotDePasse!2026", "MotDePasse!2026"],
        ),
        patch("bootstrap.capture_employee_created") as mock_capture,
        patch("builtins.print") as mock_print,
    ):
        bootstrap.main()

    mock_load_dotenv.assert_called_once_with()
    mock_monitoring.assert_called_once_with()
    created_employee = mock_capture.call_args.args[0]
    assert mock_capture.call_args.args == (
        created_employee,
        created_employee,
    )
    mock_print.assert_called_once_with(
        "Compte gestion créé avec succès : EMP-001."
    )
