import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UuidPrimaryKeyMixin
from app.models.user import User
from app.models.watchlist import UserWatchlistItem


class UserTag(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_tags"
    __table_args__ = (Index("uq_user_tags_user_name", "user_id", "name", unique=True),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    user: Mapped[User] = relationship()


class WatchlistItemTag(CreatedAtMixin, Base):
    __tablename__ = "watchlist_item_tags"

    watchlist_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_watchlist_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    item: Mapped[UserWatchlistItem] = relationship()
    tag: Mapped[UserTag] = relationship()
