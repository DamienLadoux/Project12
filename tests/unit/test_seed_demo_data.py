"""Tests du jeu de données utilisé pendant les démonstrations."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from models import Base, Client, Contract, Employee, Event, Role
from seed_demo_data import DEMO_EMPLOYEE_NUMBERS, seed_demo_data


@pytest.fixture
def demo_session():
    """Fournit une base SQLite isolée pour tester le peuplement."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@patch("seed_demo_data.hash_password", return_value="demo-password-hash")
def test_demo_seed_is_idempotent_and_covers_business_scenarios(
    mock_hash_password,
    demo_session,
):
    """Deux exécutions conservent les volumes et les scénarios attendus."""
    with demo_session.begin():
        seed_demo_data(demo_session, "DemoPassword!2026")
    with demo_session.begin():
        dataset = seed_demo_data(demo_session, "DemoPassword!2026")

    assert demo_session.scalar(select(func.count(Role.id))) == 3
    assert demo_session.scalar(select(func.count(Employee.id))) == 5
    assert demo_session.scalar(select(func.count(Client.id))) == 4
    assert demo_session.scalar(select(func.count(Contract.id))) == 4
    assert demo_session.scalar(select(func.count(Event.id))) == 3
    assert set(
        demo_session.scalars(select(Employee.employee_number))
    ) == set(DEMO_EMPLOYEE_NUMBERS)

    assert dataset.contracts["unsigned"].is_signed is False
    assert dataset.contracts["partial"].is_signed is True
    assert dataset.contracts["partial"].remaining_amount == 6000
    assert dataset.contracts["paid"].remaining_amount == 0
    assert dataset.events["green"].support is None
    assert dataset.events["horizon"].support is dataset.employees["support_1"]
    assert mock_hash_password.call_count == 10


def test_demo_seed_rejects_a_short_password(demo_session):
    """Le script refuse un mot de passe de démonstration trop faible."""
    with pytest.raises(ValueError, match="12 caractères"):
        seed_demo_data(demo_session, "trop-court")
