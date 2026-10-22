
"""Modèle SQLAlchemy représentant les collaborateurs."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.client import Client
    from models.event import Event
    from models.role import Role


class Employee(Base):
    """Collaborateur autorisé à utiliser l'application."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_number: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"),
        nullable=False,
    )

    clients: Mapped[list["Client"]] = relationship(
        back_populates="commercial"
    )

    supported_events: Mapped[list["Event"]] = relationship(
        back_populates="support"
    )

    role: Mapped["Role"] = relationship(
        back_populates="employees"
    )

    def __repr__(self) -> str:
        """Retourne une représentation lisible du collaborateur."""
        return (
            f"Employee(id={self.id!r}, "
            f"employee_number={self.employee_number!r}, "
            f"email={self.email!r})"
        )
