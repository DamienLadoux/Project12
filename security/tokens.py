"""Création et validation des jetons d'accès JWT."""

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError as JWTInvalidTokenError


JWT_ALGORITHM = "HS256"
JWT_ISSUER = "epic-events"
DEFAULT_TOKEN_LIFETIME = timedelta(hours=8)
MINIMUM_SECRET_BYTES = 32


class TokenConfigurationError(ValueError):
    """Levée lorsque le secret JWT n'est pas suffisamment robuste."""


class ExpiredAccessTokenError(PermissionError):
    """Levée lorsque la date d'expiration du jeton est dépassée."""


class InvalidAccessTokenError(PermissionError):
    """Levée lorsque le jeton est incomplet, modifié ou mal signé."""


def _validate_secret(secret: str) -> str:
    """Exige un secret d'au moins 256 bits pour la signature HMAC-SHA256."""
    if (
        not isinstance(secret, str)
        or len(secret.encode("utf-8")) < MINIMUM_SECRET_BYTES
    ):
        raise TokenConfigurationError(
            "JWT_SECRET doit contenir au moins 32 octets."
        )

    return secret


def create_access_token(
    employee_id: int,
    secret: str,
    *,
    now: datetime | None = None,
    lifetime: timedelta = DEFAULT_TOKEN_LIFETIME,
) -> str:
    """Crée un JWT identifiant un collaborateur pour une durée limitée."""
    signing_secret = _validate_secret(secret)
    if not isinstance(employee_id, int) or isinstance(employee_id, bool):
        raise ValueError("L'identifiant du collaborateur est invalide.")
    if employee_id <= 0:
        raise ValueError("L'identifiant du collaborateur est invalide.")
    if lifetime <= timedelta(0):
        raise ValueError("La durée de validité doit être positive.")

    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        raise ValueError("La date d'émission doit contenir un fuseau horaire.")

    payload = {
        "sub": str(employee_id),
        "iat": issued_at,
        "exp": issued_at + lifetime,
        "iss": JWT_ISSUER,
    }
    return jwt.encode(payload, signing_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> int:
    """Valide un JWT et retourne l'identifiant du collaborateur."""
    signing_secret = _validate_secret(secret)
    if not isinstance(token, str) or not token.strip():
        raise InvalidAccessTokenError("Le jeton d'accès est invalide.")

    try:
        payload = jwt.decode(
            token,
            signing_secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["sub", "iat", "exp", "iss"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise ExpiredAccessTokenError(
            "La session a expiré. Veuillez vous reconnecter."
        ) from error
    except JWTInvalidTokenError as error:
        raise InvalidAccessTokenError(
            "Le jeton d'accès est invalide."
        ) from error

    try:
        employee_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidAccessTokenError(
            "Le jeton ne contient pas d'identifiant valide."
        ) from error

    if employee_id <= 0:
        raise InvalidAccessTokenError(
            "Le jeton ne contient pas d'identifiant valide."
        )

    return employee_id
