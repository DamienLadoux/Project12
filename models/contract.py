
"""Modèle SQLAlchemy représentant les contrats."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.client import Client
    from models.event import Event


class Contract(Base):
    """Contrat commercial associé à un client."""

    __tablename__ = "contracts"

    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0",
            name="ck_contracts_total_amount_nonnegative",
        ),
        CheckConstraint(
            "remaining_amount >= 0",
            name="ck_contracts_remaining_amount_nonnegative",
        ),
        CheckConstraint(
            "remaining_amount <= total_amount",
            name="ck_contracts_remaining_lte_total",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id"),
        nullable=False,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    created_at: Mapped[date] = mapped_column(
        Date,
        server_default=func.current_date(),
        nullable=False,
    )
    is_signed: Mapped[bool] = mapped_column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    client: Mapped["Client"] = relationship(
        back_populates="contracts"
    )

    events: Mapped[list["Event"]] = relationship(
        back_populates="contract"
    )

    def __repr__(self) -> str:
        return (
            f"Contract(id={self.id!r}, "
            f"client_id={self.client_id!r}, "
            f"total_amount={self.total_amount!r}, "
            f"is_signed={self.is_signed!r})"
        )
