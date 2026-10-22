"""Crée un jeu de données reproductible pour les démonstrations locales."""

import argparse
import getpass
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import create_database_engine
from models import Client, Contract, Employee, Event, Role
from security.passwords import hash_password
from services.authorization import (
    COMMERCIAL_ROLE,
    MANAGEMENT_ROLE,
    SUPPORT_ROLE,
)

DEMO_EMPLOYEE_NUMBERS = (
    "MGR-DEMO",
    "COM-DEMO-1",
    "COM-DEMO-2",
    "SUP-DEMO-1",
    "SUP-DEMO-2",
)


@dataclass
class DemoDataset:
    """Entités créées ou remises dans leur état de démonstration."""

    employees: dict[str, Employee]
    clients: dict[str, Client]
    contracts: dict[str, Contract]
    events: dict[str, Event]


def _upsert_role(session: Session, name: str) -> Role:
    """Récupère un rôle existant ou le crée."""
    role = session.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        session.add(role)
    return role


def _upsert_employee(
    session: Session,
    *,
    employee_number: str,
    full_name: str,
    email: str,
    password: str,
    role: Role,
) -> Employee:
    """Crée ou réinitialise un collaborateur de démonstration."""
    employee = session.scalar(
        select(Employee).where(Employee.employee_number == employee_number)
    )
    if employee is None:
        employee = Employee(employee_number=employee_number)
        session.add(employee)

    employee.full_name = full_name
    employee.email = email
    employee.password_hash = hash_password(password)
    employee.role = role
    return employee


def _upsert_client(
    session: Session,
    *,
    email: str,
    full_name: str,
    phone: str,
    company_name: str,
    commercial: Employee,
) -> Client:
    """Crée ou réinitialise un client identifié par son e-mail de démo."""
    client = session.scalar(select(Client).where(Client.email == email))
    if client is None:
        client = Client(email=email)
        session.add(client)

    client.full_name = full_name
    client.phone = phone
    client.company_name = company_name
    client.created_at = date(2026, 1, 15)
    client.last_contact_at = date(2026, 10, 15)
    client.commercial = commercial
    return client


def _upsert_contract(
    session: Session,
    *,
    client: Client,
    total_amount: Decimal,
    remaining_amount: Decimal,
    is_signed: bool,
) -> Contract:
    """Crée ou réinitialise un contrat de démo identifié par son montant."""
    contract = session.scalar(
        select(Contract).where(
            Contract.client == client,
            Contract.total_amount == total_amount,
        )
    )
    if contract is None:
        contract = Contract(client=client, total_amount=total_amount)
        session.add(contract)

    contract.remaining_amount = remaining_amount
    contract.created_at = date(2026, 9, 1)
    contract.is_signed = is_signed
    return contract


def _upsert_event(
    session: Session,
    *,
    contract: Contract,
    name: str,
    support: Employee | None,
    start_date: datetime,
    end_date: datetime,
    location: str,
    attendees: int,
    notes: str,
) -> Event:
    """Crée ou réinitialise un événement de démonstration."""
    event = session.scalar(
        select(Event).where(Event.contract == contract, Event.name == name)
    )
    if event is None:
        event = Event(contract=contract, name=name)
        session.add(event)

    event.support = support
    event.start_date = start_date
    event.end_date = end_date
    event.location = location
    event.attendees = attendees
    event.notes = notes
    return event


def seed_demo_data(session: Session, password: str) -> DemoDataset:
    """Insère ou remet à zéro le jeu de données réservé aux démonstrations."""
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError(
            "Le mot de passe de démonstration doit contenir au moins 12 caractères."
        )

    roles = {
        name: _upsert_role(session, name)
        for name in (MANAGEMENT_ROLE, COMMERCIAL_ROLE, SUPPORT_ROLE)
    }
    employees = {
        "management": _upsert_employee(
            session,
            employee_number="MGR-DEMO",
            full_name="Morgan Gestion",
            email="gestion.demo@epic-events.test",
            password=password,
            role=roles[MANAGEMENT_ROLE],
        ),
        "commercial_1": _upsert_employee(
            session,
            employee_number="COM-DEMO-1",
            full_name="Camille Commercial",
            email="commercial1.demo@epic-events.test",
            password=password,
            role=roles[COMMERCIAL_ROLE],
        ),
        "commercial_2": _upsert_employee(
            session,
            employee_number="COM-DEMO-2",
            full_name="Charlie Commercial",
            email="commercial2.demo@epic-events.test",
            password=password,
            role=roles[COMMERCIAL_ROLE],
        ),
        "support_1": _upsert_employee(
            session,
            employee_number="SUP-DEMO-1",
            full_name="Sam Support",
            email="support1.demo@epic-events.test",
            password=password,
            role=roles[SUPPORT_ROLE],
        ),
        "support_2": _upsert_employee(
            session,
            employee_number="SUP-DEMO-2",
            full_name="Sasha Support",
            email="support2.demo@epic-events.test",
            password=password,
            role=roles[SUPPORT_ROLE],
        ),
    }
    session.flush()

    clients = {
        "nova": _upsert_client(
            session,
            email="alice@atelier-nova.test",
            full_name="Alice Martin",
            phone="01 40 00 00 01",
            company_name="Atelier Nova",
            commercial=employees["commercial_1"],
        ),
        "horizon": _upsert_client(
            session,
            email="hugo@horizon-labs.test",
            full_name="Hugo Bernard",
            phone="01 40 00 00 02",
            company_name="Horizon Labs",
            commercial=employees["commercial_1"],
        ),
        "pixel": _upsert_client(
            session,
            email="paul@pixel-forge.test",
            full_name="Paul Leroy",
            phone="01 40 00 00 03",
            company_name="Pixel Forge",
            commercial=employees["commercial_2"],
        ),
        "green": _upsert_client(
            session,
            email="gaelle@green-pulse.test",
            full_name="Gaëlle Petit",
            phone="01 40 00 00 04",
            company_name="Green Pulse",
            commercial=employees["commercial_2"],
        ),
    }
    session.flush()

    contracts = {
        "unsigned": _upsert_contract(
            session,
            client=clients["nova"],
            total_amount=Decimal("10000.00"),
            remaining_amount=Decimal("10000.00"),
            is_signed=False,
        ),
        "partial": _upsert_contract(
            session,
            client=clients["horizon"],
            total_amount=Decimal("18000.00"),
            remaining_amount=Decimal("6000.00"),
            is_signed=True,
        ),
        "paid": _upsert_contract(
            session,
            client=clients["pixel"],
            total_amount=Decimal("7500.00"),
            remaining_amount=Decimal("0.00"),
            is_signed=True,
        ),
        "without_support": _upsert_contract(
            session,
            client=clients["green"],
            total_amount=Decimal("12500.00"),
            remaining_amount=Decimal("12500.00"),
            is_signed=True,
        ),
    }
    session.flush()

    events = {
        "horizon": _upsert_event(
            session,
            contract=contracts["partial"],
            name="Démo - Gala Horizon",
            support=employees["support_1"],
            start_date=datetime(2027, 2, 10, 18, 0, tzinfo=timezone.utc),
            end_date=datetime(2027, 2, 11, 1, 0, tzinfo=timezone.utc),
            location="Palais Brongniart, Paris",
            attendees=180,
            notes="Accueil des invités à partir de 17 h 30.",
        ),
        "pixel": _upsert_event(
            session,
            contract=contracts["paid"],
            name="Démo - Lancement Pixel Forge",
            support=employees["support_2"],
            start_date=datetime(2027, 3, 5, 9, 0, tzinfo=timezone.utc),
            end_date=datetime(2027, 3, 5, 17, 0, tzinfo=timezone.utc),
            location="La Sucrière, Lyon",
            attendees=90,
            notes="Prévoir un espace de démonstration produit.",
        ),
        "green": _upsert_event(
            session,
            contract=contracts["without_support"],
            name="Démo - Forum Green Pulse",
            support=None,
            start_date=datetime(2027, 4, 12, 8, 30, tzinfo=timezone.utc),
            end_date=datetime(2027, 4, 12, 19, 0, tzinfo=timezone.utc),
            location="Parc Chanot, Marseille",
            attendees=240,
            notes="Événement volontairement sans support affecté.",
        ),
    }
    session.flush()
    return DemoDataset(employees, clients, contracts, events)


def _read_demo_password() -> str:
    """Lit le secret de démo depuis l'environnement ou le terminal."""
    password = os.getenv("DEMO_PASSWORD")
    if password:
        return password

    password = getpass.getpass("Mot de passe commun des comptes de démo : ")
    confirmation = getpass.getpass("Confirmer le mot de passe : ")
    if password != confirmation:
        raise ValueError("Les mots de passe ne correspondent pas.")
    return password


def main() -> None:
    """Confirme la cible puis remplit atomiquement la base configurée."""
    parser = argparse.ArgumentParser(
        description="Créer ou réinitialiser les données de démonstration.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="ne pas demander la confirmation de la base cible",
    )
    arguments = parser.parse_args()
    load_dotenv()

    database_name = os.getenv("DB_NAME", "base non configurée")
    if not arguments.yes:
        confirmation = input(
            f"Base cible : {database_name}. Taper DEMO pour continuer : "
        ).strip()
        if confirmation != "DEMO":
            print("Initialisation annulée.")
            return

    password = _read_demo_password()
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            with session.begin():
                dataset = seed_demo_data(session, password)
            accounts = [
                (employee.employee_number, employee.role.name)
                for employee in dataset.employees.values()
            ]
    finally:
        engine.dispose()

    print("Données de démonstration prêtes.")
    for employee_number, role_name in accounts:
        print(f"- {employee_number} ({role_name})")


if __name__ == "__main__":
    main()
