"""Initialisation des rôles et du premier compte du département gestion."""

import getpass

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import create_database_engine
from models import Employee, Role
from monitoring import capture_employee_created, configure_monitoring
from security.passwords import hash_password
from services.authorization import (
    COMMERCIAL_ROLE,
    MANAGEMENT_ROLE,
    SUPPORT_ROLE,
)
from services.validators import normalize_email, required_text

ROLE_NAMES = (MANAGEMENT_ROLE, COMMERCIAL_ROLE, SUPPORT_ROLE)


def create_initial_management_employee(
    session: Session,
    employee_number: str,
    full_name: str,
    email: str,
    password: str,
) -> Employee:
    """Crée les rôles et le premier gestionnaire sur une base vide."""
    existing_employee_id = session.scalar(select(Employee.id).limit(1))
    if existing_employee_id is not None:
        raise ValueError(
            "L'initialisation est refusée car un collaborateur existe déjà."
        )

    roles: dict[str, Role] = {}
    for role_name in ROLE_NAMES:
        role = session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name)
            session.add(role)
        roles[role_name] = role

    employee = Employee(
        employee_number=required_text(
            employee_number,
            "Le numéro d'employé est obligatoire.",
        ),
        full_name=required_text(
            full_name,
            "Le nom complet est obligatoire.",
        ),
        email=normalize_email(email),
        password_hash=hash_password(password),
        role=roles[MANAGEMENT_ROLE],
    )
    session.add(employee)
    session.flush()
    return employee


def main() -> None:
    """Demande les données initiales et les enregistre atomiquement."""
    load_dotenv()
    configure_monitoring()
    employee_number = input("Numéro du premier collaborateur : ").strip()
    full_name = input("Nom complet : ").strip()
    email = input("Adresse e-mail : ").strip()
    password = getpass.getpass("Mot de passe : ")
    confirmation = getpass.getpass("Confirmer le mot de passe : ")
    if password != confirmation:
        raise ValueError("Les mots de passe ne correspondent pas.")

    engine = create_database_engine()
    try:
        with Session(engine) as session:
            with session.begin():
                employee = create_initial_management_employee(
                    session,
                    employee_number,
                    full_name,
                    email,
                    password,
                )
            employee_number_label = employee.employee_number
            capture_employee_created(employee, employee)
    finally:
        engine.dispose()

    print(
        "Compte gestion créé avec succès : "
        f"{employee_number_label}."
    )


if __name__ == "__main__":
    main()
