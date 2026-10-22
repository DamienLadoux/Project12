"""Tests unitaires de la supervision Sentry."""

from types import SimpleNamespace
from unittest.mock import patch

from monitoring import (
    capture_contract_signature,
    capture_login,
    configure_monitoring,
)


@patch("monitoring.sentry_sdk.init")
def test_monitoring_stays_disabled_without_dsn(mock_init, monkeypatch):
    """L'application fonctionne localement sans configuration Sentry."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    assert configure_monitoring() is False
    mock_init.assert_not_called()


@patch("monitoring.sentry_sdk.init")
def test_monitoring_uses_environment_configuration(mock_init, monkeypatch):
    """Le DSN active Sentry sans collecte automatique de données privées."""
    monkeypatch.setenv("SENTRY_DSN", "https://public@example.test/1")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "test")

    assert configure_monitoring() is True
    mock_init.assert_called_once_with(
        dsn="https://public@example.test/1",
        environment="test",
        include_local_variables=False,
        send_default_pii=False,
    )


@patch("monitoring.sentry_sdk.capture_message")
@patch("monitoring.sentry_sdk.new_scope")
@patch("monitoring.sentry_sdk.set_tag")
@patch("monitoring.sentry_sdk.set_user")
def test_login_event_contains_only_technical_identity(
    mock_set_user,
    mock_set_tag,
    mock_new_scope,
    mock_capture_message,
):
    """L'audit d'une connexion n'envoie ni e-mail ni mot de passe."""
    actor = SimpleNamespace(
        id=7,
        email="private@example.test",
        role=SimpleNamespace(name="COMMERCIAL"),
    )
    scope = mock_new_scope.return_value.__enter__.return_value

    capture_login(actor)

    mock_set_user.assert_called_once_with({"id": "7"})
    mock_set_tag.assert_called_once_with("employee.role", "COMMERCIAL")
    scope.set_tag.assert_called_once_with("audit.event", "employee.login")
    mock_capture_message.assert_called_once_with(
        "employee.login",
        level="info",
    )


@patch("monitoring.sentry_sdk.capture_message")
@patch("monitoring.sentry_sdk.new_scope")
@patch("monitoring.sentry_sdk.set_tag")
@patch("monitoring.sentry_sdk.set_user")
def test_contract_signature_event_contains_entity_identifiers(
    mock_set_user,
    mock_set_tag,
    mock_new_scope,
    mock_capture_message,
):
    """La signature expose les identifiants utiles au diagnostic."""
    actor = SimpleNamespace(
        id=2,
        role=SimpleNamespace(name="GESTION"),
    )
    contract = SimpleNamespace(id=11, client_id=5)
    scope = mock_new_scope.return_value.__enter__.return_value

    capture_contract_signature(actor, contract)

    mock_set_user.assert_called_once_with({"id": "2"})
    mock_set_tag.assert_called_once_with("employee.role", "GESTION")
    scope.set_tag.assert_called_once_with("audit.event", "contract.signed")
    scope.set_context.assert_called_once_with(
        "contract",
        {"id": 11, "client_id": 5},
    )
    mock_capture_message.assert_called_once_with(
        "contract.signed",
        level="info",
    )
