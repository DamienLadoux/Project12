"""Tests unitaires des jetons d'accès JWT."""

from datetime import datetime, timedelta, timezone

import pytest

from security.tokens import (
    ExpiredAccessTokenError,
    InvalidAccessTokenError,
    TokenConfigurationError,
    create_access_token,
    decode_access_token,
)

SECRET = "a_secure_test_secret_with_32_bytes_minimum"
OTHER_SECRET = "another_secure_secret_with_32_bytes_minimum"


def test_access_token_round_trip_returns_employee_id():
    """Un jeton valide restitue uniquement l'identifiant du collaborateur."""
    token = create_access_token(42, SECRET)

    assert decode_access_token(token, SECRET) == 42


def test_expired_access_token_is_rejected():
    """La date ``exp`` empêche de réutiliser une ancienne session."""
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    token = create_access_token(
        42,
        SECRET,
        now=two_hours_ago,
        lifetime=timedelta(hours=1),
    )

    with pytest.raises(ExpiredAccessTokenError, match="expiré"):
        decode_access_token(token, SECRET)


def test_token_signed_with_another_secret_is_rejected():
    """Toute modification ou autre signature rend le jeton inutilisable."""
    token = create_access_token(42, SECRET)

    with pytest.raises(InvalidAccessTokenError, match="invalide"):
        decode_access_token(token, OTHER_SECRET)


def test_short_secret_is_rejected():
    """Une clé trop faible est refusée au lieu d'être utilisée."""
    with pytest.raises(TokenConfigurationError, match="32 octets"):
        create_access_token(42, "secret-trop-court")
