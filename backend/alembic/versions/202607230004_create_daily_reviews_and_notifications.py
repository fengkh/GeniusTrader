"""create_daily_reviews_and_notifications

Revision ID: 202607230004
Revises: 202607230003
Create Date: 2026-07-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230004"
down_revision: str | None = "202607230003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ai_tasks_ai_tasks_task_type_allowed"), "ai_tasks", type_="check")
    op.create_check_constraint(
        op.f("ck_ai_tasks_ai_tasks_task_type_allowed"),
        "ai_tasks",
        "task_type IN ('provider_connection_test', 'information_sentiment_analysis', "
        "'user_daily_review_generation')",
    )

    op.create_table(
        "daily_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('complete', 'partial', 'empty', 'failed', 'stale')",
            name=op.f("ck_daily_reviews_daily_reviews_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_daily_reviews_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_reviews")),
    )
    op.create_index("ix_daily_reviews_user_generated", "daily_reviews", ["user_id", "generated_at"])
    op.create_index("ix_daily_reviews_user_status", "daily_reviews", ["user_id", "status"])
    op.create_index("uq_daily_reviews_user_date", "daily_reviews", ["user_id", "review_date"], unique=True)

    op.create_table(
        "daily_review_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_review_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generation_mode", sa.String(length=32), nullable=False),
        sa.Column("ai_task_id", sa.Uuid(), nullable=True),
        sa.Column("rule_snapshot", sa.JSON(), nullable=False),
        sa.Column("ai_structured_result", sa.JSON(), nullable=True),
        sa.Column("ai_narrative", sa.Text(), nullable=True),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("provider_config_id", sa.Uuid(), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('complete', 'partial', 'empty', 'failed', 'stale')",
            name=op.f("ck_daily_review_versions_daily_review_versions_status_allowed"),
        ),
        sa.CheckConstraint(
            "generation_mode IN ('rules_only', 'rules_and_ai', 'rules_with_ai_fallback')",
            name=op.f("ck_daily_review_versions_daily_review_versions_generation_mode_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_task_id"],
            ["ai_tasks.id"],
            name=op.f("fk_daily_review_versions_ai_task_id_ai_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["daily_review_id"],
            ["daily_reviews.id"],
            name=op.f("fk_daily_review_versions_daily_review_id_daily_reviews"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_id"],
            ["ai_provider_configs.id"],
            name=op.f("fk_daily_review_versions_provider_config_id_ai_provider_configs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_review_versions")),
    )
    op.create_index("ix_daily_review_versions_ai_task", "daily_review_versions", ["ai_task_id"])
    op.create_index(
        "ix_daily_review_versions_review_version",
        "daily_review_versions",
        ["daily_review_id", "version_number"],
        unique=True,
    )
    op.create_foreign_key(
        op.f("fk_daily_reviews_current_version_id_daily_review_versions"),
        "daily_reviews",
        "daily_review_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "daily_review_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("daily_review_version_id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_version_id", sa.Uuid(), nullable=True),
        sa.Column("information_content_id", sa.Uuid(), nullable=True),
        sa.Column("inclusion_type", sa.String(length=32), nullable=False),
        sa.Column("inclusion_reason", sa.String(length=300), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("relation_scope", sa.String(length=40), nullable=False),
        sa.Column("relation_status_snapshot", sa.JSON(), nullable=False),
        sa.Column("is_watchlist_related", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "inclusion_type IN ('analyzed', 'pending_analysis', 'analysis_failed', "
            "'content_insufficient', 'unconfirmed_relation')",
            name=op.f("ck_daily_review_items_daily_review_items_inclusion_type_allowed"),
        ),
        sa.CheckConstraint(
            "relation_scope IN ('watchlist_stock', 'confirmed_non_watchlist_stock', 'unassigned', 'entity_only')",
            name=op.f("ck_daily_review_items_daily_review_items_relation_scope_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_version_id"],
            ["information_analysis_versions.id"],
            name=op.f("fk_daily_review_items_analysis_version_id_information_analysis_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["daily_review_version_id"],
            ["daily_review_versions.id"],
            name=op.f("fk_daily_review_items_daily_review_version_id_daily_review_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["information_content_id"],
            ["information_contents.id"],
            name=op.f("fk_daily_review_items_information_content_id_information_contents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_daily_review_items_information_item_id_information_items"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_review_items")),
    )
    op.create_index("ix_daily_review_items_effective_date", "daily_review_items", ["effective_date"])
    op.create_index("ix_daily_review_items_information", "daily_review_items", ["information_item_id"])
    op.create_index(
        "ix_daily_review_items_version_item",
        "daily_review_items",
        ["daily_review_version_id", "information_item_id"],
        unique=True,
    )

    op.create_table(
        "business_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("event_version", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('user_daily_review.generated', 'user_daily_review.partial', "
            "'user_daily_review.failed', 'user_daily_review.became_stale', "
            "'information.high_priority_detected', 'information.verification_required', 'ai_task.failed')",
            name=op.f("ck_business_events_business_events_event_type_allowed"),
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'notice', 'important')",
            name=op.f("ck_business_events_business_events_severity_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_business_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_events")),
    )
    op.create_index("ix_business_events_subject", "business_events", ["subject_type", "subject_id"])
    op.create_index("ix_business_events_user_created", "business_events", ["user_id", "created_at"])
    op.create_index("ix_business_events_user_type", "business_events", ["user_id", "event_type"])
    op.create_index("uq_business_events_idempotency_key", "business_events", ["idempotency_key"], unique=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("deep_link", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "severity IN ('info', 'notice', 'important')",
            name=op.f("ck_notifications_notifications_severity_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('unread', 'read', 'archived', 'expired')",
            name=op.f("ck_notifications_notifications_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["business_events.id"],
            name=op.f("fk_notifications_event_id_business_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index("ix_notifications_user_event_type", "notifications", ["user_id", "event_type"])
    op.create_index("ix_notifications_user_status_created", "notifications", ["user_id", "status", "created_at"])
    op.create_index("uq_notifications_user_event", "notifications", ["user_id", "event_id"], unique=True)

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("minimum_severity", sa.String(length=32), nullable=False),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "channel IN ('in_app')",
            name=op.f("ck_notification_preferences_notification_preferences_channel_allowed"),
        ),
        sa.CheckConstraint(
            "frequency IN ('immediate', 'daily_digest', 'disabled')",
            name=op.f("ck_notification_preferences_notification_preferences_frequency_allowed"),
        ),
        sa.CheckConstraint(
            "minimum_severity IN ('info', 'notice', 'important')",
            name=op.f("ck_notification_preferences_notification_preferences_minimum_severity_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preferences")),
    )
    op.create_index("ix_notification_preferences_user", "notification_preferences", ["user_id"])
    op.create_index(
        "uq_notification_preferences_user_event_channel",
        "notification_preferences",
        ["user_id", "event_type", "channel"],
        unique=True,
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("deduplication_key", sa.String(length=200), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "channel IN ('in_app')",
            name=op.f("ck_notification_deliveries_notification_deliveries_channel_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'skipped', 'failed')",
            name=op.f("ck_notification_deliveries_notification_deliveries_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name=op.f("fk_notification_deliveries_notification_id_notifications"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_deliveries_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_deliveries")),
    )
    op.create_index("ix_notification_deliveries_notification", "notification_deliveries", ["notification_id"])
    op.create_index("ix_notification_deliveries_user_status", "notification_deliveries", ["user_id", "status"])
    op.create_index(
        "uq_notification_deliveries_deduplication",
        "notification_deliveries",
        ["deduplication_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_notification_deliveries_deduplication", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_user_status", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_notification", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("uq_notification_preferences_user_event_channel", table_name="notification_preferences")
    op.drop_index("ix_notification_preferences_user", table_name="notification_preferences")
    op.drop_table("notification_preferences")
    op.drop_index("uq_notifications_user_event", table_name="notifications")
    op.drop_index("ix_notifications_user_status_created", table_name="notifications")
    op.drop_index("ix_notifications_user_event_type", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("uq_business_events_idempotency_key", table_name="business_events")
    op.drop_index("ix_business_events_user_type", table_name="business_events")
    op.drop_index("ix_business_events_user_created", table_name="business_events")
    op.drop_index("ix_business_events_subject", table_name="business_events")
    op.drop_table("business_events")
    op.drop_index("ix_daily_review_items_version_item", table_name="daily_review_items")
    op.drop_index("ix_daily_review_items_information", table_name="daily_review_items")
    op.drop_index("ix_daily_review_items_effective_date", table_name="daily_review_items")
    op.drop_table("daily_review_items")
    op.drop_constraint(
        op.f("fk_daily_reviews_current_version_id_daily_review_versions"),
        "daily_reviews",
        type_="foreignkey",
    )
    op.drop_index("ix_daily_review_versions_review_version", table_name="daily_review_versions")
    op.drop_index("ix_daily_review_versions_ai_task", table_name="daily_review_versions")
    op.drop_table("daily_review_versions")
    op.drop_index("uq_daily_reviews_user_date", table_name="daily_reviews")
    op.drop_index("ix_daily_reviews_user_status", table_name="daily_reviews")
    op.drop_index("ix_daily_reviews_user_generated", table_name="daily_reviews")
    op.drop_table("daily_reviews")

    op.drop_constraint(op.f("ck_ai_tasks_ai_tasks_task_type_allowed"), "ai_tasks", type_="check")
    op.create_check_constraint(
        op.f("ck_ai_tasks_ai_tasks_task_type_allowed"),
        "ai_tasks",
        "task_type IN ('provider_connection_test', 'information_sentiment_analysis')",
    )
