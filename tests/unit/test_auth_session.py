"""Tests unitaires de l'authentification persistante."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models import Employee, Role
from security.token_store import load_token, save_token
from security.tokens import ExpiredAccessTokenError, create_access_token
from services.auth_session import (
    AuthenticationRequiredError,
    InvalidCredentialsError,
    get_current_actor,
    login,
    logout,
)


SECRET = "a_secure_test_secret_with_32_bytes_minimum"


def employee(employee_id: int = 42) -> Employee:
    """Construit un collaborateur persistant simulé pour les tests."""
    authenticated_employee = Employee(
        employee_number="EMP-042",
        full_name="Alice Martin",
        email="alice@example.test",
        password_hash="argon_hash",
        role=Role(name="GESTION"),
    )
    authenticated_employee.id = employee_id
    return authenticated_employee


@patch("services.auth_session.authenticate_employee")
def test_login_persists_token(mock_authenticate, tmp_path: Path):
    """Une authentification correcte produit une session réutilisable."""
    authenticated_employee = employee()
    mock_authenticate.return_value = authenticated_employee
    token_path = tmp_path / "access_token"

    result = login(
        MagicMock(),
        "EMP-042",
        "correct-password",
        SECRET,
        token_path=token_path,
    )

    assert result is authenticated_employee
    assert load_token(token_path)
    mock_authenticate.assert_called_once()


@patch("services.auth_session.authenticate_employee", return_value=None)
def test_login_rejects_invalid_credentials(mock_authenticate, tmp_path: Path):
    """Un échec ne crée aucun fichier de session."""
    token_path = tmp_path / "access_token"

    with pytest.raises(InvalidCredentialsError):
        login(
            MagicMock(),
            "EMP-042",
            "wrong-password",
            SECRET,
            token_path=token_path,
        )

    assert not token_path.exists()


def test_current_actor_is_reloaded_from_database(tmp_path: Path):
    """Le JWT donne l'id, mais le rôle courant provient toujours de la base."""
    token_path = tmp_path / "access_token"
    save_token(create_access_token(42, SECRET), token_path)
    current_employee = employee()
    session = MagicMock()
    session.get.return_value = current_employee

    actor = get_current_actor(session, SECRET, token_path=token_path)

    assert actor is current_employee
    session.get.assert_called_once_with(Employee, 42)


def test_expired_token_is_deleted(tmp_path: Path):
    """Une session expirée oblige une nouvelle connexion et est nettoyée."""
    token_path = tmp_path / "access_token"
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    expired_token = create_access_token(
        42,
        SECRET,
        now=two_hours_ago,
        lifetime=timedelta(hours=1),
    )
    save_token(expired_token, token_path)

    with pytest.raises(ExpiredAccessTokenError):
        get_current_actor(MagicMock(), SECRET, token_path=token_path)

    assert not token_path.exists()


def test_deleted_employee_invalidates_persistent_session(tmp_path: Path):
    """Un JWT valide ne maintient pas l'accès d'un compte supprimé."""
    token_path = tmp_path / "access_token"
    save_token(create_access_token(42, SECRET), token_path)
    session = MagicMock()
    session.get.return_value = None

    with pytest.raises(AuthenticationRequiredError, match="n'existe plus"):
        get_current_actor(session, SECRET, token_path=token_path)

    assert not token_path.exists()


def test_missing_session_requires_login(tmp_path: Path):
    """Sans jeton local, aucune reconstruction d'actor n'est possible."""
    session = MagicMock()

    with pytest.raises(AuthenticationRequiredError, match="login"):
        get_current_actor(
            session,
            SECRET,
            token_path=tmp_path / "missing_token",
        )

    session.get.assert_not_called()


def test_logout_removes_local_session(tmp_path: Path):
    """La déconnexion supprime uniquement le jeton de la machine."""
    token_path = tmp_path / "access_token"
    save_token("header.payload.signature", token_path)

    assert logout(token_path=token_path)
    assert not token_path.exists()
