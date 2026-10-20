
"""Tests unitaires du script d'initialisation de la base."""

from unittest.mock import MagicMock, patch

import pytest

import init_database


@patch("init_database.create_engine")
@patch("init_database.load_dotenv")
def test_database_already_exists_does_not_create_it(
    mock_load_dotenv,
    mock_create_engine,
    monkeypatch,
):
    """Une base existante ne doit pas être recréée."""
    monkeypatch.setenv("ADMIN_DB_NAME", "postgres")
    monkeypatch.setenv("ADMIN_DB_USER", "admin")
    monkeypatch.setenv("ADMIN_DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_NAME", "epic_events")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")

    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = (
        mock_connection
    )
    mock_connection.execute.return_value.scalar_one_or_none.return_value = 1
    mock_create_engine.return_value = mock_engine

    with patch("builtins.print") as mock_print:
        init_database.main()

    mock_connection.exec_driver_sql.assert_not_called()
    mock_print.assert_called_once_with(
        "La base 'epic_events' existe déjà."
    )
    mock_engine.dispose.assert_called_once()


@patch("init_database.load_dotenv")
def test_missing_admin_password_raises_error(mock_load_dotenv, monkeypatch):
    """Le script refuse de démarrer si le mot de passe admin manque."""
    monkeypatch.setenv("ADMIN_DB_NAME", "postgres")
    monkeypatch.setenv("ADMIN_DB_USER", "admin")
    monkeypatch.delenv("ADMIN_DB_PASSWORD", raising=False)
    monkeypatch.setenv("DB_NAME", "epic_events")

    with pytest.raises(ValueError, match="ADMIN_DB_PASSWORD"):
        init_database.main()


@patch("init_database.load_dotenv")
def test_admin_database_cannot_be_target_database(
    mock_load_dotenv,
    monkeypatch,
):
    """La base cible ne peut pas être la base administrative."""
    monkeypatch.setenv("ADMIN_DB_NAME", "epic_events")
    monkeypatch.setenv("ADMIN_DB_USER", "admin")
    monkeypatch.setenv("ADMIN_DB_PASSWORD", "test_password")
    monkeypatch.setenv("DB_NAME", "epic_events")

    with pytest.raises(ValueError, match="différente"):
        init_database.main()
