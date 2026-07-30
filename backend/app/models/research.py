import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin
from app.models.information import InformationAnalysisVersion, InformationItem
from app.models.review_notification import DailyReview, DailyReviewVersion
from app.models.stock import Stock
from app.models.user import User

RESEARCH_TASK_TYPE_VALUES = (
    "'verification', 'observation', 'follow_up', 'missing_document', 'user_note'"
)
RESEARCH_TASK_STATUS_VALUES = (
    "'pending', 'monitoring', 'confirmed', 'disproved', 'partially_confirmed', "
    "'unable_to_determine', 'no_longer_applicable', 'dismissed'"
)
RESEARCH_TASK_PRIORITY_VALUES = "'low', 'medium', 'high'"
RESEARCH_TASK_SOURCE_TYPE_VALUES = (
    "'user', 'information_analysis', 'daily_review', 'announcement', 'system_rule'"
)
RESEARCH_TASK_CREATED_BY_VALUES = "'user', 'system'"


class ResearchTask(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_tasks"
    __table_args__ = (
        CheckConstraint(
            f"task_type IN ({RESEARCH_TASK_TYPE_VALUES})",
            name="research_tasks_task_type_allowed",
        ),
        CheckConstraint(
            f"status IN ({RESEARCH_TASK_STATUS_VALUES})",
            name="research_tasks_status_allowed",
        ),
        CheckConstraint(
            f"priority IN ({RESEARCH_TASK_PRIORITY_VALUES})",
            name="research_tasks_priority_allowed",
        ),
        CheckConstraint(
            f"source_type IN ({RESEARCH_TASK_SOURCE_TYPE_VALUES})",
            name="research_tasks_source_type_allowed",
        ),
        CheckConstraint(
            f"created_by IN ({RESEARCH_TASK_CREATED_BY_VALUES})",
            name="research_tasks_created_by_allowed",
        ),
        Index("ix_research_tasks_user_status", "user_id", "status", "updated_at"),
        Index("ix_research_tasks_user_type", "user_id", "task_type", "status"),
        Index("ix_research_tasks_user_due", "user_id", "due_date", "status"),
        Index("ix_research_tasks_stock_status", "stock_id", "status"),
        Index(
            "uq_research_tasks_user_deduplication_key",
            "user_id",
            "deduplication_key",
            unique=True,
            postgresql_where=text("deduplication_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    stock_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stocks.id", ondelete="RESTRICT"),
    )
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="user")
    source_information_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="SET NULL"),
    )
    source_analysis_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_analysis_versions.id", ondelete="SET NULL"),
    )
    source_daily_review_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("daily_reviews.id", ondelete="SET NULL"),
    )
    source_daily_review_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("daily_review_versions.id", ondelete="SET NULL"),
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    current_evidence_summary: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    deduplication_key: Mapped[str | None] = mapped_column(String(200))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    stock: Mapped[Stock | None] = relationship()
    source_information_item: Mapped[InformationItem | None] = relationship()
    source_analysis_version: Mapped[InformationAnalysisVersion | None] = relationship()
    source_daily_review: Mapped[DailyReview | None] = relationship()
    source_daily_review_version: Mapped[DailyReviewVersion | None] = relationship()
    updates: Mapped[list["ResearchTaskUpdate"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="ResearchTaskUpdate.created_at",
    )


class ResearchTaskUpdate(UuidPrimaryKeyMixin, Base):
    __tablename__ = "research_task_updates"
    __table_args__ = (
        CheckConstraint(
            f"previous_status IS NULL OR previous_status IN ({RESEARCH_TASK_STATUS_VALUES})",
            name="research_task_updates_previous_status_allowed",
        ),
        CheckConstraint(
            f"new_status IN ({RESEARCH_TASK_STATUS_VALUES})",
            name="research_task_updates_new_status_allowed",
        ),
        CheckConstraint(
            f"created_by IN ({RESEARCH_TASK_CREATED_BY_VALUES})",
            name="research_task_updates_created_by_allowed",
        ),
        Index("ix_research_task_updates_task_created", "task_id", "created_at"),
        Index("ix_research_task_updates_user_created", "user_id", "created_at"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    evidence_information_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_items.id", ondelete="SET NULL"),
    )
    evidence_analysis_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("information_analysis_versions.id", ondelete="SET NULL"),
    )
    evidence_daily_review_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("daily_review_versions.id", ondelete="SET NULL"),
    )
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    task: Mapped[ResearchTask] = relationship(back_populates="updates")
    user: Mapped[User] = relationship()
    evidence_information_item: Mapped[InformationItem | None] = relationship()
    evidence_analysis_version: Mapped[InformationAnalysisVersion | None] = relationship()
    evidence_daily_review_version: Mapped[DailyReviewVersion | None] = relationship()
