"""Orchestration de l'authentification persistante des collaborateurs."""

from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from models import Employee
from security.token_store import (
    StoredTokenNotFoundError,
    delete_token,
    load_token,
    save_token,
)
from security.tokens import (
    DEFAULT_TOKEN_LIFETIME,
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
)
from services.authentication import authenticate_employee


class InvalidCredentialsError(PermissionError):
    """Levée lorsque l'identifiant ou le mot de passe est incorrect."""


class AuthenticationRequiredError(PermissionError):
    """Levée lorsqu'aucun compte valide n'est associé à la session."""


def login(
    session: Session,
    identifier: str,
    password: str,
    secret: str,
    *,
    token_path: Path | None = None,
    now: datetime | None = None,
    lifetime: timedelta = DEFAULT_TOKEN_LIFETIME,
) -> Employee:
    """Authentifie un collaborateur et persiste un JWT sur sa machine."""
    employee = authenticate_employee(session, identifier, password)
    if employee is None:
        raise InvalidCredentialsError(
            "Identifiant ou mot de passe incorrect."
        )
    if employee.id is None:
        raise ValueError(
            "Le collaborateur doit être enregistré avant la connexion."
        )

    token = create_access_token(
        employee.id,
        secret,
        now=now,
        lifetime=lifetime,
    )
    save_token(token, token_path)
    return employee


def get_current_actor(
    session: Session,
    secret: str,
    *,
    token_path: Path | None = None,
) -> Employee:
    """Reconstruit l'acteur courant depuis le JWT et la base de données."""
    try:
        token = load_token(token_path)
    except StoredTokenNotFoundError as error:
        raise AuthenticationRequiredError(str(error)) from error

    try:
        employee_id = decode_access_token(token, secret)
    except (ExpiredAccessTokenError, InvalidAccessTokenError):
        delete_token(token_path)
        raise

    employee = session.get(Employee, employee_id)
    if employee is None:
        delete_token(token_path)
        raise AuthenticationRequiredError(
            "Le compte associé à la session n'existe plus."
        )

    return employee


def logout(*, token_path: Path | None = None) -> bool:
    """Ferme la session locale en supprimant son jeton."""
    return delete_token(token_path)
