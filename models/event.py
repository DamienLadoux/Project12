
"""Modèle SQLAlchemy représentant les événements."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.contract import Contract
    from models.employee import Employee


class Event(Base):
    """Événement organisé dans le cadre d'un contrat."""

    __tablename__ = "events"

    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="ck_events_end_date_gte_start_date",
        ),
        CheckConstraint(
            "attendees >= 0",
            name="ck_events_attendees_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id"),
        nullable=False,
    )
    support_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    attendees: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped["Contract"] = relationship(
        back_populates="events"
    )
    support: Mapped["Employee | None"] = relationship(
        back_populates="supported_events"
    )

    def __repr__(self) -> str:
        return (
            f"Event(id={self.id!r}, "
            f"name={self.name!r}, "
            f"contract_id={self.contract_id!r})"
        )
