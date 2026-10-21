"""Tests unitaires du stockage local du jeton."""

from pathlib import Path

import pytest

from security.token_store import (
    StoredTokenNotFoundError,
    delete_token,
    load_token,
    save_token,
)


def test_token_can_be_saved_loaded_and_deleted(tmp_path: Path):
    """Le fichier permet de conserver la session entre deux commandes."""
    token_path = tmp_path / "session" / "access_token"

    saved_path = save_token("header.payload.signature", token_path)

    assert saved_path == token_path
    assert load_token(token_path) == "header.payload.signature"
    assert delete_token(token_path)
    assert not token_path.exists()
    assert not delete_token(token_path)


def test_missing_token_has_an_explicit_error(tmp_path: Path):
    """L'absence de fichier correspond à une session non ouverte."""
    with pytest.raises(StoredTokenNotFoundError, match="login"):
        load_token(tmp_path / "missing_token")


def test_empty_token_is_rejected(tmp_path: Path):
    """Un fichier présent mais vide n'est pas considéré comme une session."""
    token_path = tmp_path / "access_token"
    token_path.write_text("   ", encoding="utf-8")

    with pytest.raises(StoredTokenNotFoundError):
        load_token(token_path)
