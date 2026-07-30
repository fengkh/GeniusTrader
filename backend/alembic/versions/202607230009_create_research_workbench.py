"""create_research_workbench

Revision ID: 202607230009
Revises: 202607230008
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230009"
down_revision: str | None = "202607230008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TASK_TYPE_VALUES = "'verification', 'observation', 'follow_up', 'missing_document', 'user_note'"
TASK_STATUS_VALUES = (
    "'pending', 'monitoring', 'confirmed', 'disproved', 'partially_confirmed', "
    "'unable_to_determine', 'no_longer_applicable', 'dismissed'"
)
TASK_PRIORITY_VALUES = "'low', 'medium', 'high'"
TASK_SOURCE_TYPE_VALUES = "'user', 'information_analysis', 'daily_review', 'announcement', 'system_rule'"
CREATED_BY_VALUES = "'user', 'system'"
BUSINESS_EVENT_TYPES = (
    "'user_daily_review.generated', 'user_daily_review.partial', "
    "'user_daily_review.failed', 'user_daily_review.became_stale', "
    "'information.high_priority_detected', 'information.verification_required', "
    "'ai_task.failed', 'research_task.created', 'research_task.status_changed', "
    "'research_task.due', 'observation_condition.due'"
)


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_business_events_business_events_event_type_allowed"),
        "business_events",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_business_events_business_events_event_type_allowed"),
        "business_events",
        f"event_type IN ({BUSINESS_EVENT_TYPES})",
    )

    op.create_table(
        "research_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stock_id", sa.Uuid(), nullable=True),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_information_item_id", sa.Uuid(), nullable=True),
        sa.Column("source_analysis_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_daily_review_id", sa.Uuid(), nullable=True),
        sa.Column("source_daily_review_version_id", sa.Uuid(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("current_evidence_summary", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("deduplication_key", sa.String(length=200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(f"task_type IN ({TASK_TYPE_VALUES})", name=op.f("ck_research_tasks_research_tasks_task_type_allowed")),
        sa.CheckConstraint(f"status IN ({TASK_STATUS_VALUES})", name=op.f("ck_research_tasks_research_tasks_status_allowed")),
        sa.CheckConstraint(f"priority IN ({TASK_PRIORITY_VALUES})", name=op.f("ck_research_tasks_research_tasks_priority_allowed")),
        sa.CheckConstraint(
            f"source_type IN ({TASK_SOURCE_TYPE_VALUES})",
            name=op.f("ck_research_tasks_research_tasks_source_type_allowed"),
        ),
        sa.CheckConstraint(
            f"created_by IN ({CREATED_BY_VALUES})",
            name=op.f("ck_research_tasks_research_tasks_created_by_allowed"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_research_tasks_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], name=op.f("fk_research_tasks_stock_id_stocks"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_information_item_id"],
            ["information_items.id"],
            name=op.f("fk_research_tasks_source_information_item_id_information_items"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_analysis_version_id"],
            ["information_analysis_versions.id"],
            name=op.f("fk_research_tasks_source_analysis_version_id_information_analysis_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_review_id"],
            ["daily_reviews.id"],
            name=op.f("fk_research_tasks_source_daily_review_id_daily_reviews"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_daily_review_version_id"],
            ["daily_review_versions.id"],
            name=op.f("fk_research_tasks_source_daily_review_version_id_daily_review_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_tasks")),
    )
    op.create_index("ix_research_tasks_user_status", "research_tasks", ["user_id", "status", "updated_at"])
    op.create_index("ix_research_tasks_user_type", "research_tasks", ["user_id", "task_type", "status"])
    op.create_index("ix_research_tasks_user_due", "research_tasks", ["user_id", "due_date", "status"])
    op.create_index("ix_research_tasks_stock_status", "research_tasks", ["stock_id", "status"])
    op.create_index(
        "uq_research_tasks_user_deduplication_key",
        "research_tasks",
        ["user_id", "deduplication_key"],
        unique=True,
        postgresql_where=sa.text("deduplication_key IS NOT NULL"),
    )

    op.create_table(
        "research_task_updates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("evidence_information_item_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_analysis_version_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_daily_review_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"previous_status IS NULL OR previous_status IN ({TASK_STATUS_VALUES})",
            name=op.f("ck_research_task_updates_research_task_updates_previous_status_allowed"),
        ),
        sa.CheckConstraint(
            f"new_status IN ({TASK_STATUS_VALUES})",
            name=op.f("ck_research_task_updates_research_task_updates_new_status_allowed"),
        ),
        sa.CheckConstraint(
            f"created_by IN ({CREATED_BY_VALUES})",
            name=op.f("ck_research_task_updates_research_task_updates_created_by_allowed"),
        ),
        sa.ForeignKeyConstraint(["task_id"], ["research_tasks.id"], name=op.f("fk_research_task_updates_task_id_research_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_research_task_updates_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["evidence_information_item_id"],
            ["information_items.id"],
            name=op.f("fk_research_task_updates_evidence_information_item_id_information_items"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_analysis_version_id"],
            ["information_analysis_versions.id"],
            name=op.f("fk_research_task_updates_evidence_analysis_version_id_information_analysis_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_daily_review_version_id"],
            ["daily_review_versions.id"],
            name=op.f("fk_research_task_updates_evidence_daily_review_version_id_daily_review_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_task_updates")),
    )
    op.create_index(
        "ix_research_task_updates_task_created",
        "research_task_updates",
        ["task_id", "created_at"],
    )
    op.create_index(
        "ix_research_task_updates_user_created",
        "research_task_updates",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_task_updates_user_created", table_name="research_task_updates")
    op.drop_index("ix_research_task_updates_task_created", table_name="research_task_updates")
    op.drop_table("research_task_updates")
    op.drop_index("uq_research_tasks_user_deduplication_key", table_name="research_tasks")
    op.drop_index("ix_research_tasks_stock_status", table_name="research_tasks")
    op.drop_index("ix_research_tasks_user_due", table_name="research_tasks")
    op.drop_index("ix_research_tasks_user_type", table_name="research_tasks")
    op.drop_index("ix_research_tasks_user_status", table_name="research_tasks")
    op.drop_table("research_tasks")

    op.drop_constraint(
        op.f("ck_business_events_business_events_event_type_allowed"),
        "business_events",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_business_events_business_events_event_type_allowed"),
        "business_events",
        (
            "event_type IN ('user_daily_review.generated', 'user_daily_review.partial', "
            "'user_daily_review.failed', 'user_daily_review.became_stale', "
            "'information.high_priority_detected', 'information.verification_required', "
            "'ai_task.failed')"
        ),
    )
