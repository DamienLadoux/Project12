"""Intégration entre JWT, stockage local et session applicative."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models import Employee, Role
from security.token_store import load_token, save_token
from security.tokens import ExpiredAccessTokenError, create_access_token
from services.auth_session import (
    AuthenticationRequiredError,
    get_current_actor,
    login,
)


SECRET = "a_secure_test_secret_with_32_bytes_minimum"


def employee(employee_id: int = 42) -> Employee:
    """Construit le collaborateur simulé renvoyé par la base."""
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
def test_login_persists_a_reusable_token(mock_authenticate, tmp_path: Path):
    """Une connexion produit un JWT lisible par une commande suivante."""
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


def test_token_reloads_current_actor_from_database(tmp_path: Path):
    """Le JWT fournit l'id, tandis que le compte courant vient de la base."""
    token_path = tmp_path / "access_token"
    save_token(create_access_token(42, SECRET), token_path)
    current_employee = employee()
    session = MagicMock()
    session.get.return_value = current_employee

    actor = get_current_actor(session, SECRET, token_path=token_path)

    assert actor is current_employee
    session.get.assert_called_once_with(Employee, 42)


def test_expired_token_is_rejected_and_removed(tmp_path: Path):
    """Une session expirée oblige une nouvelle authentification."""
    token_path = tmp_path / "access_token"
    expired_token = create_access_token(
        42,
        SECRET,
        now=datetime.now(timezone.utc) - timedelta(hours=2),
        lifetime=timedelta(hours=1),
    )
    save_token(expired_token, token_path)

    with pytest.raises(ExpiredAccessTokenError):
        get_current_actor(MagicMock(), SECRET, token_path=token_path)

    assert not token_path.exists()


def test_deleted_account_invalidates_existing_token(tmp_path: Path):
    """Un jeton valide ne conserve pas l'accès d'un compte supprimé."""
    token_path = tmp_path / "access_token"
    save_token(create_access_token(42, SECRET), token_path)
    session = MagicMock()
    session.get.return_value = None

    with pytest.raises(AuthenticationRequiredError, match="n'existe plus"):
        get_current_actor(session, SECRET, token_path=token_path)

    assert not token_path.exists()
