"""Intégration du stockage de session avec le système de fichiers."""

from pathlib import Path

import pytest

from security.token_store import (
    StoredTokenNotFoundError,
    delete_token,
    load_token,
    save_token,
)


def test_token_lifecycle_on_filesystem(tmp_path: Path):
    """Le jeton peut être sauvegardé, relu puis supprimé."""
    token_path = tmp_path / "session" / "access_token"

    save_token("header.payload.signature", token_path)

    assert load_token(token_path) == "header.payload.signature"
    assert delete_token(token_path)
    assert not token_path.exists()


def test_missing_token_means_no_active_session(tmp_path: Path):
    """L'absence du fichier est traduite en erreur applicative explicite."""
    with pytest.raises(StoredTokenNotFoundError, match="login"):
        load_token(tmp_path / "missing_token")
