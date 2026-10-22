"""Tests unitaires du raccordement entre la CLI et les services."""

import argparse
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from epicevents import (
    EntityNotFoundError,
    _capture_audit_event,
    _dispatch_business_command,
    _iso_date,
    _iso_datetime,
    _nonnegative_integer,
    _positive_integer,
    _run_business_command,
    build_parser,
    main,
)
from models import Client


def parse(*arguments: str):
    """Analyse une commande comme si elle provenait du terminal."""
    return build_parser().parse_args(list(arguments))


def test_parser_rejects_nonpositive_entity_identifier():
    """Un identifiant nul est rejeté avant toute ouverture de session."""
    with pytest.raises(SystemExit) as error:
        parse("clients", "update", "0", "--name", "Test")

    assert error.value.code == 2


@pytest.mark.parametrize(
    ("validator", "value"),
    [
        (_positive_integer, "invalid"),
        (_positive_integer, "0"),
        (_nonnegative_integer, "invalid"),
        (_nonnegative_integer, "-1"),
        (_iso_date, "2026-99-99"),
        (_iso_datetime, "invalid"),
        (_iso_datetime, "2026-10-22T10:00:00"),
    ],
)
def test_cli_value_validators_reject_invalid_input(validator, value):
    """Les valeurs incorrectes sont converties en erreurs argparse."""
    with pytest.raises(argparse.ArgumentTypeError):
        validator(value)


def test_cli_value_validators_accept_boundary_values():
    """Les valeurs limites valides sont normalisées."""
    assert _positive_integer("1") == 1
    assert _nonnegative_integer("0") == 0
    assert _iso_date("2026-10-22") == date(2026, 10, 22)
    assert _iso_datetime("2026-10-22T10:00:00Z") == datetime(
        2026,
        10,
        22,
        10,
        tzinfo=timezone.utc,
    )


@patch("epicevents.create_employee")
@patch("epicevents.getpass.getpass", return_value="secure-password")
def test_employee_password_is_prompted_outside_command_history(
    mock_getpass,
    mock_create_employee,
):
    """La CLI demande le mot de passe puis appelle le service de création."""
    session = MagicMock()
    actor = object()
    mock_create_employee.return_value = SimpleNamespace(id=12)
    arguments = parse(
        "employees",
        "create",
        "--number",
        "EMP-012",
        "--name",
        "Alice Martin",
        "--email",
        "alice@example.test",
        "--role",
        "SUPPORT",
    )

    audit_event = _dispatch_business_command(session, actor, arguments)

    mock_create_employee.assert_called_once_with(
        session,
        actor,
        "EMP-012",
        "Alice Martin",
        "alice@example.test",
        "secure-password",
        "SUPPORT",
    )
    assert audit_event == (
        "employee.created",
        mock_create_employee.return_value,
    )


@patch("epicevents.update_employee")
def test_employee_update_is_returned_as_audit_event(mock_update_employee):
    """Une modification remonte le collaborateur à journaliser."""
    session = MagicMock()
    actor = object()
    employee = SimpleNamespace(id=12)
    session.get.return_value = employee
    arguments = parse("employees", "update", "12", "--name", "Alice")

    audit_event = _dispatch_business_command(session, actor, arguments)

    mock_update_employee.assert_called_once_with(
        session,
        actor,
        employee,
        full_name="Alice",
    )
    assert audit_event == ("employee.updated", employee)


@patch("epicevents.update_client")
def test_client_update_passes_only_explicit_options(mock_update_client):
    """Une option absente est ignorée et --clear-phone transmet None."""
    session = MagicMock()
    actor = object()
    client = object()
    session.get.return_value = client
    arguments = parse(
        "clients",
        "update",
        "7",
        "--name",
        "Nouveau nom",
        "--clear-phone",
        "--last-contact",
        "2026-10-21",
    )

    _dispatch_business_command(session, actor, arguments)

    mock_update_client.assert_called_once_with(
        session,
        actor,
        client,
        full_name="Nouveau nom",
        phone=None,
        last_contact_at=date(2026, 10, 21),
    )


def test_unknown_entity_stops_command_before_mutation():
    """Un identifiant absent est refusé avant d'appeler le service."""
    session = MagicMock()
    session.get.return_value = None
    arguments = parse("clients", "update", "404", "--name", "Test")

    with pytest.raises(EntityNotFoundError, match="404"):
        _dispatch_business_command(session, object(), arguments)


@patch("epicevents.update_contract")
def test_contract_signature_is_returned_as_audit_target(mock_update_contract):
    """Une transition vers signé remonte le contrat à journaliser."""
    session = MagicMock()
    actor = object()
    contract = SimpleNamespace(id=7, is_signed=False)
    session.get.return_value = contract

    def sign_contract(*_args, **_kwargs):
        contract.is_signed = True
        return contract

    mock_update_contract.side_effect = sign_contract
    arguments = parse("contracts", "update", "7", "--signed")

    audit_target = _dispatch_business_command(session, actor, arguments)

    assert audit_target == ("contract.signed", contract)


def test_contract_already_signed_is_not_returned_as_audit_target():
    """Une autre modification ne duplique pas l'événement de signature."""
    session = MagicMock()
    contract = SimpleNamespace(id=7, is_signed=True)
    session.get.return_value = contract
    arguments = parse("contracts", "update", "7", "--remaining", "0")

    with patch("epicevents.update_contract"):
        audit_target = _dispatch_business_command(
            session,
            object(),
            arguments,
        )

    assert audit_target is None


@pytest.mark.parametrize(
    ("event_name", "capture_name"),
    [
        ("employee.created", "capture_employee_created"),
        ("employee.updated", "capture_employee_updated"),
        ("contract.signed", "capture_contract_signature"),
    ],
)
def test_audit_event_routes_to_matching_monitor(event_name, capture_name):
    """Chaque événement différé utilise le bon appel Sentry."""
    actor = object()
    entity = object()

    with patch(f"epicevents.{capture_name}") as mock_capture:
        _capture_audit_event(actor, (event_name, entity))

    mock_capture.assert_called_once_with(actor, entity)


@patch("epicevents._dispatch_business_command")
@patch("epicevents.get_current_actor")
@patch("epicevents.create_database_engine")
@patch("epicevents.Session")
@patch("epicevents._jwt_secret", return_value="secure-secret")
def test_business_command_uses_authenticated_transaction(
    mock_secret,
    mock_session_class,
    mock_create_engine,
    mock_get_actor,
    mock_dispatch,
):
    """La commande restaure actor puis s'exécute dans session.begin()."""
    engine = mock_create_engine.return_value
    session_manager = MagicMock()
    session = MagicMock()
    session_manager.__enter__.return_value = session
    mock_session_class.return_value = session_manager
    actor = SimpleNamespace(
        id=1,
        role=SimpleNamespace(name="COMMERCIAL"),
    )
    mock_get_actor.return_value = actor
    employee = SimpleNamespace(id=12)
    audit_event = ("employee.created", employee)
    mock_dispatch.return_value = audit_event
    arguments = parse("clients", "list")

    with patch("epicevents._capture_audit_event") as mock_capture_audit:
        _run_business_command(arguments)

    session.begin.assert_called_once_with()
    mock_get_actor.assert_called_once_with(session, "secure-secret")
    mock_dispatch.assert_called_once_with(session, actor, arguments)
    mock_capture_audit.assert_called_once_with(actor, audit_event)
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize(
    ("argv", "runner_name"),
    [
        (["login", "EMP-001"], "_run_login"),
        (["whoami"], "_run_whoami"),
        (["clients", "list"], "_run_business_command"),
    ],
)
def test_main_routes_valid_commands(argv, runner_name):
    """Le point d'entrée distribue chaque famille de commandes."""
    with (
        patch("epicevents.load_dotenv"),
        patch("epicevents.configure_monitoring"),
        patch(f"epicevents.{runner_name}") as mock_runner,
    ):
        result = main(argv)

    assert result == 0
    mock_runner.assert_called_once()


@pytest.mark.parametrize(
    ("token_deleted", "printer_name", "message"),
    [
        (True, "print_success", "Déconnexion réussie."),
        (False, "print_info", "Aucune session active."),
    ],
)
def test_main_reports_logout_state(token_deleted, printer_name, message):
    """La déconnexion distingue un jeton supprimé de son absence."""
    with (
        patch("epicevents.load_dotenv"),
        patch("epicevents.configure_monitoring"),
        patch("epicevents.logout", return_value=token_deleted),
        patch(f"epicevents.{printer_name}") as mock_print,
    ):
        result = main(["logout"])

    assert result == 0
    mock_print.assert_called_once_with(message)


@pytest.mark.parametrize(
    "error",
    [
        ValueError("Donnée invalide"),
        IntegrityError("statement", {}, RuntimeError("conflict")),
    ],
)
def test_main_turns_expected_errors_into_failure_status(error):
    """Les erreurs prévues sont affichées sans trace Python."""
    with (
        patch("epicevents.load_dotenv"),
        patch("epicevents.configure_monitoring"),
        patch("epicevents._run_whoami", side_effect=error),
        patch("epicevents.print_error") as mock_print_error,
    ):
        result = main(["whoami"])

    assert result == 1
    mock_print_error.assert_called_once()
