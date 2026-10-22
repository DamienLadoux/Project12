"""Tests unitaires du raccordement entre la CLI et les services."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from epicevents import (
    EntityNotFoundError,
    _dispatch_business_command,
    _run_business_command,
    build_parser,
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

    _dispatch_business_command(session, actor, arguments)

    mock_create_employee.assert_called_once_with(
        session,
        actor,
        "EMP-012",
        "Alice Martin",
        "alice@example.test",
        "secure-password",
        "SUPPORT",
    )


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

    assert audit_target is contract


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
    mock_dispatch.return_value = None
    arguments = parse("clients", "list")

    _run_business_command(arguments)

    session.begin.assert_called_once_with()
    mock_get_actor.assert_called_once_with(session, "secure-secret")
    mock_dispatch.assert_called_once_with(session, actor, arguments)
    engine.dispose.assert_called_once_with()
