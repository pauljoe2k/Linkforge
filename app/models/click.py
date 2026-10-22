from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.link import Link

DEVICE_TYPES = ("desktop", "mobile", "tablet", "other")


class Click(Base):
    __tablename__ = "clicks"
    __table_args__ = (
        # Analytics hot path: per-day buckets, date ranges, totals.
        Index("ix_clicks_link_id_clicked_at", "link_id", "clicked_at"),
        CheckConstraint("device_type IN ('desktop', 'mobile', 'tablet', 'other')",
                        name="ck_clicks_device_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    link_id: Mapped[int] = mapped_column(
        ForeignKey("links.id", ondelete="CASCADE"), nullable=False
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    device_type: Mapped[str] = mapped_column(String(16), nullable=False)

    link: Mapped["Link"] = relationship(back_populates="clicks")
