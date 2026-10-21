"""Tests unitaires des requêtes de consultation du CRM."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.authorization import AuthorizationError
from services.query_service import list_clients, list_contracts, list_events


def persisted_actor(role_name: str, actor_id: int = 7):
    """Construit un acteur authentifié possédant un identifiant en base."""
    return SimpleNamespace(
        id=actor_id,
        role=SimpleNamespace(name=role_name),
    )


def session_returning(*objects):
    """Construit une session simulant le résultat de ``scalars().all()``."""
    session = MagicMock()
    session.scalars.return_value.all.return_value = list(objects)
    return session


@pytest.mark.parametrize(
    "query_function",
    [list_clients, list_contracts, list_events],
)
def test_queries_require_an_authenticated_actor(query_function):
    """Aucune consultation n'est lancée sans utilisateur authentifié."""
    session = MagicMock()

    with pytest.raises(AuthorizationError, match="authentification"):
        query_function(session, None)

    session.scalars.assert_not_called()


def test_authenticated_actor_can_list_all_clients():
    """La couche renvoie une liste construite depuis le résultat SQLAlchemy."""
    expected_clients = [object(), object()]
    session = session_returning(*expected_clients)

    clients = list_clients(session, persisted_actor("SUPPORT"))

    assert clients == expected_clients
    statement = session.scalars.call_args.args[0]
    assert statement.whereclause is None


def test_commercial_can_filter_owned_clients():
    """Le filtre traduit l'identifiant de l'acteur en clause SQL WHERE."""
    session = session_returning()

    list_clients(
        session,
        persisted_actor("COMMERCIAL", actor_id=42),
        mine_only=True,
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "clients.commercial_id = 42" in compiled


def test_non_commercial_cannot_use_owned_clients_filter():
    """Un filtre métier non pertinent est refusé avant la requête."""
    session = MagicMock()

    with pytest.raises(AuthorizationError, match="commerciaux"):
        list_clients(
            session,
            persisted_actor("GESTION"),
            mine_only=True,
        )

    session.scalars.assert_not_called()


def test_contract_filters_can_be_combined():
    """Les contrats peuvent être filtrés simultanément par trois critères."""
    session = session_returning()

    list_contracts(
        session,
        persisted_actor("COMMERCIAL", actor_id=42),
        mine_only=True,
        unsigned_only=True,
        unpaid_only=True,
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "clients.commercial_id = 42" in compiled
    assert "contracts.is_signed IS false" in compiled
    assert "contracts.remaining_amount > 0" in compiled


def test_support_can_filter_assigned_events():
    """Le filtre du support utilise l'identifiant de l'acteur connecté."""
    session = session_returning()

    list_events(
        session,
        persisted_actor("SUPPORT", actor_id=21),
        mine_only=True,
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "events.support_id = 21" in compiled


def test_events_without_support_can_be_filtered():
    """La gestion peut repérer les événements encore non affectés."""
    session = session_returning()

    list_events(
        session,
        persisted_actor("GESTION"),
        without_support_only=True,
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "events.support_id IS NULL" in compiled
