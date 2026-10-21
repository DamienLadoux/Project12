"""Opérations métier protégées sur les collaborateurs."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Employee, Role
from security.passwords import hash_password
from services.authorization import AuthorizationError, can_manage_employees
from services.validators import normalize_email, required_text


class UnknownRoleError(ValueError):
    """Levée lorsqu'un rôle demandé n'existe pas dans la base."""


class EmployeeInUseError(ValueError):
    """Levée lorsqu'un collaborateur est encore responsable de données."""


def create_employee(
    session: Session,
    actor: Employee | None,
    employee_number: str,
    full_name: str,
    email: str,
    password: str,
    role_name: str,
) -> Employee:
    """Crée un collaborateur pour un acteur du département gestion.

    La fonction ajoute et valide l'objet dans la transaction en cours, mais
    laisse le ``commit`` à l'appelant.
    """
    if not can_manage_employees(actor):
        raise AuthorizationError(
            "Seul le département gestion peut créer un collaborateur."
        )

    normalized_employee_number = required_text(
        employee_number,
        "Le numéro d'employé est obligatoire.",
    )
    normalized_full_name = required_text(
        full_name,
        "Le nom complet est obligatoire.",
    )
    normalized_email = normalize_email(email)
    normalized_role_name = required_text(
        role_name,
        "Le rôle est obligatoire.",
    )

    role = session.scalar(
        select(Role).where(Role.name == normalized_role_name)
    )
    if role is None:
        raise UnknownRoleError("Le rôle demandé n'existe pas.")

    employee = Employee(
        employee_number=normalized_employee_number,
        full_name=normalized_full_name,
        email=normalized_email,
        password_hash=hash_password(password),
        role=role,
    )
    session.add(employee)
    session.flush()

    return employee


def update_employee(
    session: Session,
    actor: Employee | None,
    employee: Employee,
    *,
    full_name: str | None = None,
    email: str | None = None,
    password: str | None = None,
    role_name: str | None = None,
) -> Employee:
    """Met à jour les données administratives d'un collaborateur.

    Le numéro d'employé reste inchangé : il constitue l'identifiant
    professionnel unique du collaborateur. Seuls les champs explicitement
    fournis sont modifiés.
    """
    if not can_manage_employees(actor):
        raise AuthorizationError(
            "Seul le département gestion peut modifier un collaborateur."
        )

    if all(value is None for value in (full_name, email, password, role_name)):
        raise ValueError("Au moins une donnée doit être fournie.")

    if full_name is not None:
        employee.full_name = required_text(
            full_name,
            "Le nom complet est obligatoire.",
        )
    if email is not None:
        employee.email = normalize_email(email)
    if password is not None:
        employee.password_hash = hash_password(password)
    if role_name is not None:
        normalized_role_name = required_text(
            role_name,
            "Le rôle est obligatoire.",
        )
        role = session.scalar(
            select(Role).where(Role.name == normalized_role_name)
        )
        if role is None:
            raise UnknownRoleError("Le rôle demandé n'existe pas.")
        employee.role = role

    session.flush()
    return employee


def delete_employee(
    session: Session,
    actor: Employee | None,
    employee: Employee,
) -> None:
    """Supprime un collaborateur qui ne référence aucune donnée métier.

    Un collaborateur encore responsable d'un client ou d'un événement ne peut
    pas être supprimé : sa responsabilité doit d'abord être transférée.
    """
    if not can_manage_employees(actor):
        raise AuthorizationError(
            "Seul le département gestion peut supprimer un collaborateur."
        )

    if employee.clients or employee.supported_events:
        raise EmployeeInUseError(
            "Le collaborateur est encore responsable de données métier."
        )

    session.delete(employee)
    session.flush()
