
"""Modèle SQLAlchemy représentant les rôles des collaborateurs."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Role(Base):
    """Rôle attribué à un collaborateur."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
    )

    employees: Mapped[list["Employee"]] = relationship(
        back_populates="role"
    )

    def __repr__(self) -> str:
        """Retourne une représentation lisible du rôle."""
        return f"Role(id={self.id!r}, name={self.name!r})"
