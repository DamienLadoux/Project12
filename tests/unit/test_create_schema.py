"""Tests unitaires de la création des tables SQLAlchemy."""

from unittest.mock import MagicMock, patch

import pytest

import create_schema


@patch("create_schema.Base.metadata.create_all")
@patch("create_schema.create_engine")
@patch("create_schema.load_dotenv")
def test_schema_creation_uses_configured_engine_and_disposes_it(
    mock_load_dotenv,
    mock_create_engine,
    mock_create_all,
    monkeypatch,
):
    """Le schéma est créé sur la base configurée puis le moteur est fermé."""
    monkeypatch.setenv("DB_USER", "epic_events_user")
    monkeypatch.setenv("DB_PASSWORD", "database-password")
    monkeypatch.setenv("DB_HOST", "db.example.test")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "epic_events")
    engine = MagicMock()
    mock_create_engine.return_value = engine

    with patch("builtins.print") as mock_print:
        create_schema.main()

    mock_load_dotenv.assert_called_once_with()
    database_url = mock_create_engine.call_args.args[0]
    assert database_url.username == "epic_events_user"
    assert database_url.password == "database-password"
    assert database_url.host == "db.example.test"
    assert database_url.port == 5433
    assert database_url.database == "epic_events"
    mock_create_all.assert_called_once_with(engine)
    mock_print.assert_called_once_with("Création du schéma terminée.")
    engine.dispose.assert_called_once_with()


@patch("create_schema.Base.metadata.create_all", side_effect=RuntimeError)
@patch("create_schema.create_engine")
@patch("create_schema.load_dotenv")
def test_schema_creation_disposes_engine_after_failure(
    mock_load_dotenv,
    mock_create_engine,
    mock_create_all,
):
    """Le moteur est également fermé lorsqu'une création échoue."""
    engine = MagicMock()
    mock_create_engine.return_value = engine

    with pytest.raises(RuntimeError):
        create_schema.main()

    engine.dispose.assert_called_once_with()
