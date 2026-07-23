"""create_information_and_ai_analysis

Revision ID: 202607230002
Revises: 202607230001
Create Date: 2026-07-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230002"
down_revision: str | None = "202607230001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("api_style", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("extra_headers_encrypted", sa.Text(), nullable=True),
        sa.Column("last_test_status", sa.String(length=50), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "api_style IN ('openai_chat_completions')",
            name=op.f("ck_ai_provider_configs_ai_provider_configs_api_style_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_provider_configs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_provider_configs")),
    )
    op.create_index("ix_ai_provider_configs_user_id", "ai_provider_configs", ["user_id"])
    op.create_index(
        "uq_ai_provider_configs_one_enabled",
        "ai_provider_configs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("enabled = true"),
    )

    op.create_table(
        "ai_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("provider_config_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "task_type IN ('provider_connection_test', 'information_sentiment_analysis')",
            name=op.f("ck_ai_tasks_ai_tasks_task_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name=op.f("ck_ai_tasks_ai_tasks_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_id"],
            ["ai_provider_configs.id"],
            name=op.f("fk_ai_tasks_provider_config_id_ai_provider_configs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_ai_tasks_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_tasks")),
    )
    op.create_index("ix_ai_tasks_target", "ai_tasks", ["target_type", "target_id"])
    op.create_index("ix_ai_tasks_user_status", "ai_tasks", ["user_id", "status"])

    op.create_table(
        "ai_task_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_http_status", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_detail_redacted", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_ai_task_attempts_ai_task_attempts_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_task_id"],
            ["ai_tasks.id"],
            name=op.f("fk_ai_task_attempts_ai_task_id_ai_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_task_attempts")),
    )
    op.create_index("ix_ai_task_attempts_task_number", "ai_task_attempts", ["ai_task_id", "attempt_number"], unique=True)

    op.create_table(
        "information_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("input_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("is_important", sa.Boolean(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "input_type IN ('manual_text', 'public_url')",
            name=op.f("ck_information_items_information_items_input_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'fetching', 'fetch_failed', 'ready', 'analyzing', "
            "'analyzed', 'analysis_failed', 'archived')",
            name=op.f("ck_information_items_information_items_status_allowed"),
        ),
        sa.CheckConstraint(
            "source_type IN ('announcement', 'news', 'social', 'analyst_opinion', 'user_note', 'unknown')",
            name=op.f("ck_information_items_information_items_source_type_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_information_items_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information_items")),
    )
    op.create_index("ix_information_items_user_created", "information_items", ["user_id", "created_at"])
    op.create_index("ix_information_items_user_source", "information_items", ["user_id", "source_type"])
    op.create_index("ix_information_items_user_status", "information_items", ["user_id", "status"])

    op.create_table(
        "information_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column("url_hash", sa.String(length=64), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("author", sa.String(length=200), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("fetch_status", sa.String(length=32), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "fetch_status IN ('pending', 'succeeded', 'failed', 'skipped')",
            name=op.f("ck_information_sources_information_sources_fetch_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_information_sources_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_information_sources_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information_sources")),
    )
    op.create_index("ix_information_sources_item_id", "information_sources", ["information_item_id"])
    op.create_index("ix_information_sources_user_url_hash", "information_sources", ["user_id", "url_hash"], unique=True)

    op.create_table(
        "information_contents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("content_origin", sa.String(length=32), nullable=False),
        sa.Column("extracted_title", sa.String(length=300), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(length=80), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_origin IN ('user_input', 'fetched_page', 'user_correction')",
            name=op.f("ck_information_contents_information_contents_origin_allowed"),
        ),
        sa.CheckConstraint(
            "extraction_status IN ('succeeded', 'failed', 'insufficient')",
            name=op.f("ck_information_contents_information_contents_extraction_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_information_contents_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information_contents")),
    )
    op.create_index("ix_information_contents_content_hash", "information_contents", ["content_hash"])
    op.create_index(
        "ix_information_contents_item_version",
        "information_contents",
        ["information_item_id", "content_version"],
        unique=True,
    )

    op.create_table(
        "content_fetch_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("response_bytes", sa.Integer(), nullable=True),
        sa.Column("final_url", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_content_fetch_attempts_content_fetch_attempts_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_content_fetch_attempts_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_fetch_attempts")),
    )
    op.create_index(
        "ix_content_fetch_attempts_item_number",
        "content_fetch_attempts",
        ["information_item_id", "attempt_number"],
        unique=True,
    )

    op.create_table(
        "information_analysis_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("ai_task_id", sa.Uuid(), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("provider_config_id", sa.Uuid(), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("analysis_status", sa.String(length=32), nullable=False),
        sa.Column("structured_result", sa.JSON(), nullable=False),
        sa.Column("raw_response_redacted", sa.Text(), nullable=True),
        sa.Column("input_content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "analysis_status IN ('succeeded', 'failed')",
            name=op.f("ck_information_analysis_versions_information_analysis_versions_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["ai_task_id"],
            ["ai_tasks.id"],
            name=op.f("fk_information_analysis_versions_ai_task_id_ai_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_information_analysis_versions_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_config_id"],
            ["ai_provider_configs.id"],
            name=op.f("fk_information_analysis_versions_provider_config_id_ai_provider_configs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information_analysis_versions")),
    )
    op.create_index("ix_information_analysis_versions_task_id", "information_analysis_versions", ["ai_task_id"])
    op.create_index(
        "ix_information_analysis_versions_item_version",
        "information_analysis_versions",
        ["information_item_id", "version_number"],
        unique=True,
    )

    op.create_table(
        "information_stock_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("stock_id", sa.Uuid(), nullable=False),
        sa.Column("relation_origin", sa.String(length=32), nullable=False),
        sa.Column("relation_status", sa.String(length=32), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_text", sa.String(length=500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "relation_origin IN ('ai', 'user', 'rule')",
            name=op.f("ck_information_stock_relations_information_stock_relations_origin_allowed"),
        ),
        sa.CheckConstraint(
            "relation_status IN ('suggested', 'confirmed', 'rejected')",
            name=op.f("ck_information_stock_relations_information_stock_relations_status_allowed"),
        ),
        sa.CheckConstraint(
            "relation_type IN ('directly_related', 'indirectly_related', 'mentioned', 'compared', "
            "'supply_chain', 'competitor', 'unknown')",
            name=op.f("ck_information_stock_relations_information_stock_relations_type_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_information_stock_relations_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_information_stock_relations_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information_stock_relations")),
    )
    op.create_index("ix_information_stock_relations_item", "information_stock_relations", ["information_item_id"])
    op.create_index("ix_information_stock_relations_stock", "information_stock_relations", ["stock_id"])

    op.create_table(
        "information_entity_mentions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("relation", sa.String(length=120), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_text", sa.String(length=500), nullable=True),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "entity_type IN ('company', 'industry', 'concept', 'product', 'person', 'organization', "
            "'commodity', 'policy', 'location', 'unknown')",
            name=op.f("ck_information_entity_mentions_information_entity_mentions_type_allowed"),
        ),
        sa.CheckConstraint(
            "origin IN ('ai', 'user', 'rule')",
            name=op.f("ck_information_entity_mentions_information_entity_mentions_origin_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('suggested', 'confirmed', 'rejected')",
            name=op.f("ck_information_entity_mentions_information_entity_mentions_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_information_entity_mentions_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information_entity_mentions")),
    )
    op.create_index("ix_information_entity_mentions_item", "information_entity_mentions", ["information_item_id"])

    op.create_table(
        "verification_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_version_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("verification_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("evidence_needed", sa.Text(), nullable=True),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('pending', 'verified', 'contradicted', 'unresolved', 'dismissed')",
            name=op.f("ck_verification_items_verification_items_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["analysis_version_id"],
            ["information_analysis_versions.id"],
            name=op.f("fk_verification_items_analysis_version_id_information_analysis_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_verification_items_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verification_items")),
    )
    op.create_index("ix_verification_items_item_status", "verification_items", ["information_item_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_verification_items_item_status", table_name="verification_items")
    op.drop_table("verification_items")
    op.drop_index("ix_information_entity_mentions_item", table_name="information_entity_mentions")
    op.drop_table("information_entity_mentions")
    op.drop_index("ix_information_stock_relations_stock", table_name="information_stock_relations")
    op.drop_index("ix_information_stock_relations_item", table_name="information_stock_relations")
    op.drop_table("information_stock_relations")
    op.drop_index("ix_information_analysis_versions_item_version", table_name="information_analysis_versions")
    op.drop_index("ix_information_analysis_versions_task_id", table_name="information_analysis_versions")
    op.drop_table("information_analysis_versions")
    op.drop_index("ix_content_fetch_attempts_item_number", table_name="content_fetch_attempts")
    op.drop_table("content_fetch_attempts")
    op.drop_index("ix_information_contents_item_version", table_name="information_contents")
    op.drop_index("ix_information_contents_content_hash", table_name="information_contents")
    op.drop_table("information_contents")
    op.drop_index("ix_information_sources_user_url_hash", table_name="information_sources")
    op.drop_index("ix_information_sources_item_id", table_name="information_sources")
    op.drop_table("information_sources")
    op.drop_index("ix_information_items_user_status", table_name="information_items")
    op.drop_index("ix_information_items_user_source", table_name="information_items")
    op.drop_index("ix_information_items_user_created", table_name="information_items")
    op.drop_table("information_items")
    op.drop_index("ix_ai_task_attempts_task_number", table_name="ai_task_attempts")
    op.drop_table("ai_task_attempts")
    op.drop_index("ix_ai_tasks_user_status", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_target", table_name="ai_tasks")
    op.drop_table("ai_tasks")
    op.drop_index("uq_ai_provider_configs_one_enabled", table_name="ai_provider_configs")
    op.drop_index("ix_ai_provider_configs_user_id", table_name="ai_provider_configs")
    op.drop_table("ai_provider_configs")
