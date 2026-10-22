"""Tests unitaires du service d'authentification."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.authentication import authenticate_employee


@patch("services.authentication.verify_password", return_value=True)
def test_authenticate_employee_returns_employee_for_valid_credentials(
    mock_verify_password,
):
    """Un collaborateur est retourné lorsque ses identifiants sont valides."""
    employee = SimpleNamespace(password_hash="stored_hash")
    session = MagicMock()
    session.scalar.return_value = employee

    authenticated_employee = authenticate_employee(
        session,
        "EMP-001",
        "MotDePasseTest!2026",
    )

    assert authenticated_employee is employee
    mock_verify_password.assert_called_once_with(
        "MotDePasseTest!2026",
        "stored_hash",
    )


@patch("services.authentication.verify_password", return_value=False)
def test_authenticate_employee_rejects_an_invalid_password(
    mock_verify_password,
):
    """Un mot de passe invalide ne donne pas accès au collaborateur."""
    session = MagicMock()
    session.scalar.return_value = SimpleNamespace(password_hash="stored_hash")

    authenticated_employee = authenticate_employee(
        session,
        "EMP-001",
        "MotDePasseIncorrect!2026",
    )

    assert authenticated_employee is None
    mock_verify_password.assert_called_once()


@patch("services.authentication.verify_password")
def test_authenticate_employee_rejects_an_unknown_identifier(
    mock_verify_password,
):
    """Un identifiant inconnu ne révèle aucune information sur les comptes."""
    session = MagicMock()
    session.scalar.return_value = None

    authenticated_employee = authenticate_employee(
        session,
        "inconnu@example.test",
        "MotDePasseTest!2026",
    )

    assert authenticated_employee is None
    mock_verify_password.assert_not_called()


@patch("services.authentication.verify_password", return_value=True)
def test_authenticate_employee_normalizes_email_case(mock_verify_password):
    """La connexion par e-mail n'est pas sensible aux majuscules."""
    employee = SimpleNamespace(password_hash="stored_hash")
    session = MagicMock()
    session.scalar.return_value = employee

    authenticated_employee = authenticate_employee(
        session,
        " ALICE@EXAMPLE.TEST ",
        "MotDePasseTest!2026",
    )

    assert authenticated_employee is employee
    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "alice@example.test" in compiled
