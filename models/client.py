
"""Modèle SQLAlchemy représentant les clients."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.contract import Contract
    from models.employee import Employee


class Client(Base):
    """Client suivi par un collaborateur commercial."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    company_name: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )
    created_at: Mapped[date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )
    last_contact_at: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    commercial_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False
    )
    commercial: Mapped["Employee"] = relationship(
        back_populates="clients"
    )
    contracts: Mapped[list["Contract"]] = relationship(
        back_populates="client"
    )

    def __repr__(self) -> str:
        return (
            f"Client(id={self.id!r}, "
            f"full_name={self.full_name!r}, "
            f"email={self.email!r})"
        )
