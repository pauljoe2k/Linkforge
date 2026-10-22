from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.click import Click
    from app.models.user import User

MAX_SLUG_LENGTH = 64
MAX_URL_LENGTH = 2048


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (
        # Owner's list view: filter by user_id, order by created_at DESC.
        # (A plain b-tree on (user_id, created_at) is traversable backwards,
        # so no DESC in the index definition is needed.)
        Index("ix_links_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(
        String(MAX_SLUG_LENGTH), unique=True, nullable=False, index=True
    )
    target_url: Mapped[str] = mapped_column(String(MAX_URL_LENGTH), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="links")
    clicks: Mapped[list["Click"]] = relationship(
        back_populates="link", cascade="all, delete-orphan", passive_deletes=True
    )
