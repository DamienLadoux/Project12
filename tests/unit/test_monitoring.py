"""Tests unitaires de la supervision Sentry."""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sentry_sdk.integrations.logging import LoggingIntegration

from monitoring import (
    capture_contract_signature,
    capture_employee_created,
    capture_employee_updated,
    capture_login,
    configure_monitoring,
    scrub_sentry_event,
    trace_command,
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
    monkeypatch.setenv("SENTRY_RELEASE", "epic-events@test")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")

    assert configure_monitoring() is True
    mock_init.assert_called_once()
    options = dict(mock_init.call_args.kwargs)
    integrations = options.pop("integrations")
    assert len(integrations) == 1
    integration = integrations[0]
    assert isinstance(integration, LoggingIntegration)
    assert integration._sentry_logs_handler.level == logging.INFO
    assert integration._breadcrumb_handler.level == logging.INFO
    assert integration._handler.level == logging.ERROR
    assert LoggingIntegration.capture_sentry_logs is True
    assert options == {
        "dsn": "https://public@example.test/1",
        "before_send": scrub_sentry_event,
        "before_send_transaction": scrub_sentry_event,
        "environment": "test",
        "include_local_variables": False,
        "release": "epic-events@test",
        "send_default_pii": False,
        "traces_sample_rate": 0.25,
    }


def test_sentry_scrubber_removes_cli_arguments_only():
    """Les valeurs métier passées en CLI ne quittent pas l'application."""
    event = {
        "extra": {
            "sys.argv": ["clients", "create", "private@example.test"],
            "safe_key": "safe-value",
        },
        "message": "test",
    }

    scrubbed_event = scrub_sentry_event(event)

    assert scrubbed_event == {
        "extra": {"safe_key": "safe-value"},
        "message": "test",
    }


@patch("monitoring.sentry_sdk.start_transaction")
def test_trace_command_names_cli_transaction(mock_start_transaction):
    """Chaque commande reçoit un nom de transaction stable et lisible."""
    trace_command("whoami")

    mock_start_transaction.assert_called_once_with(
        op="cli.command",
        name="epicevents whoami",
    )


@patch("monitoring.logger.info")
@patch("monitoring.sentry_sdk.new_scope")
@patch("monitoring.sentry_sdk.set_tag")
@patch("monitoring.sentry_sdk.set_user")
def test_login_event_contains_only_technical_identity(
    mock_set_user,
    mock_set_tag,
    mock_new_scope,
    mock_log_info,
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
    mock_log_info.assert_called_once_with(
        "employee.login",
        extra={
            "audit_event": "employee.login",
            "employee_id": 7,
            "employee_role": "COMMERCIAL",
        },
    )


@pytest.mark.parametrize(
    ("capture_function", "event_name"),
    [
        (capture_employee_created, "employee.created"),
        (capture_employee_updated, "employee.updated"),
    ],
)
def test_employee_write_event_contains_only_technical_data(
    capture_function,
    event_name,
):
    """L'audit d'un collaborateur exclut nom, e-mail et mot de passe."""
    actor = SimpleNamespace(
        id=2,
        role=SimpleNamespace(name="GESTION"),
    )
    employee = SimpleNamespace(
        id=9,
        full_name="Donnée privée",
        email="private@example.test",
        password_hash="secret-hash",
        role=SimpleNamespace(name="SUPPORT"),
    )

    with (
        patch("monitoring.sentry_sdk.set_user") as mock_set_user,
        patch("monitoring.sentry_sdk.set_tag") as mock_set_tag,
        patch("monitoring.sentry_sdk.new_scope") as mock_new_scope,
        patch(
            "monitoring.logger.info"
        ) as mock_log_info,
    ):
        scope = mock_new_scope.return_value.__enter__.return_value

        capture_function(actor, employee)

    mock_set_user.assert_called_once_with({"id": "2"})
    mock_set_tag.assert_called_once_with("employee.role", "GESTION")
    scope.set_tag.assert_called_once_with("audit.event", event_name)
    scope.set_context.assert_called_once_with(
        "employee",
        {"id": 9, "role": "SUPPORT"},
    )
    mock_log_info.assert_called_once_with(
        event_name,
        extra={
            "audit_event": event_name,
            "employee_id": 9,
            "employee_role": "SUPPORT",
        },
    )


@patch("monitoring.logger.info")
@patch("monitoring.sentry_sdk.new_scope")
@patch("monitoring.sentry_sdk.set_tag")
@patch("monitoring.sentry_sdk.set_user")
def test_contract_signature_event_contains_entity_identifiers(
    mock_set_user,
    mock_set_tag,
    mock_new_scope,
    mock_log_info,
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
    mock_log_info.assert_called_once_with(
        "contract.signed",
        extra={
            "audit_event": "contract.signed",
            "contract_id": 11,
            "client_id": 5,
        },
    )
