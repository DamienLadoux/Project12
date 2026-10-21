"""Authentification des collaborateurs."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models import Employee
from security.passwords import verify_password


def authenticate_employee(
    session: Session,
    identifier: str,
    password: str,
) -> Employee | None:
    """Retourne le collaborateur si ses identifiants sont valides.

    Le même résultat ``None`` est renvoyé pour un identifiant inconnu et pour
    un mot de passe invalide afin de ne pas exposer la cause de l'échec.
    """
    if not isinstance(identifier, str) or not isinstance(password, str):
        return None

    normalized_identifier = identifier.strip()
    if not normalized_identifier or not password:
        return None

    normalized_email_identifier = normalized_identifier.lower()

    statement = select(Employee).where(
        or_(
            Employee.employee_number == normalized_identifier,
            Employee.email == normalized_email_identifier,
        )
    )
    employee = session.scalar(statement)

    if employee is None:
        return None

    if not verify_password(password, employee.password_hash):
        return None

    return employee
