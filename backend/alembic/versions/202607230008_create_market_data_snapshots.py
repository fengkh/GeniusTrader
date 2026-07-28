"""create_market_data_snapshots

Revision ID: 202607230008
Revises: 202607230007
Create Date: 2026-07-28 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230008"
down_revision: str | None = "202607230007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MARKET_DATA_AUTHORIZATION_VALUES = (
    "'unverified', 'personal_development_only', 'commercial_evaluation', "
    "'commercially_authorized', 'prohibited', 'expired'"
)

PROVIDER_HEALTH_VALUES = (
    "'unknown', 'pass', 'partial', 'data_insufficient', 'not_available', "
    "'network_error', 'timeout', 'rate_limited', 'access_denied', 'source_changed', "
    "'parse_error', 'content_unavailable', 'legal_hold', 'disabled'"
)


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "market_data_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("authorization_status", sa.String(length=40), nullable=False),
        sa.Column("usage_scope", sa.JSON(), nullable=False),
        sa.Column("production_enabled", sa.Boolean(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("last_health_status", sa.String(length=40), nullable=False),
        sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("limitations", sa.JSON(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "source_type IN ('official_exchange', 'third_party_data_service', 'development_mock')",
            name=op.f("ck_market_data_sources_market_data_sources_type_allowed"),
        ),
        sa.CheckConstraint(
            f"authorization_status IN ({MARKET_DATA_AUTHORIZATION_VALUES})",
            name=op.f("ck_market_data_sources_market_data_sources_authorization_allowed"),
        ),
        sa.CheckConstraint(
            f"last_health_status IN ({PROVIDER_HEALTH_VALUES})",
            name=op.f("ck_market_data_sources_market_data_sources_health_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_data_sources")),
    )
    op.create_index(
        "uq_market_data_sources_source_code",
        "market_data_sources",
        ["source_code"],
        unique=True,
    )
    op.create_index(
        "ix_market_data_sources_production_enabled",
        "market_data_sources",
        ["production_enabled"],
    )

    op.create_table(
        "market_data_sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("sync_mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_trade_date", sa.Date(), nullable=True),
        sa.Column("resolved_trade_date", sa.Date(), nullable=True),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("requested_symbol_count", sa.Integer(), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "trigger_type IN ('manual_admin', 'cli', 'scheduled', 'dry_run')",
            name=op.f("ck_market_data_sync_runs_market_data_sync_runs_trigger_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'complete', 'partial', 'failed', 'data_insufficient', "
            "'not_available', 'network_error', 'timeout', 'rate_limited', 'access_denied', "
            "'source_changed', 'parse_error', 'content_unavailable', 'legal_hold', 'disabled')",
            name=op.f("ck_market_data_sync_runs_market_data_sync_runs_status_allowed"),
        ),
        sa.CheckConstraint(
            "sync_mode IN ('latest_completed_trade_day', 'selected_trade_date', 'optional_backfill')",
            name=op.f("ck_market_data_sync_runs_market_data_sync_runs_mode_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_data_sync_runs")),
    )
    op.create_index(
        "ix_market_data_sync_runs_source_started",
        "market_data_sync_runs",
        ["source_code", "started_at"],
    )
    op.create_index(
        "ix_market_data_sync_runs_requested_date",
        "market_data_sync_runs",
        ["requested_trade_date"],
    )
    op.create_index(
        "ix_market_data_sync_runs_resolved_date",
        "market_data_sync_runs",
        ["resolved_trade_date"],
    )
    op.create_index(
        "uq_market_data_sync_runs_active_source_date",
        "market_data_sync_runs",
        ["source_code", "resolved_trade_date"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "stock_daily_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stock_id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=True),
        sa.Column("high", sa.Numeric(18, 6), nullable=True),
        sa.Column("low", sa.Numeric(18, 6), nullable=True),
        sa.Column("close", sa.Numeric(18, 6), nullable=True),
        sa.Column("pre_close", sa.Numeric(18, 6), nullable=True),
        sa.Column("change", sa.Numeric(18, 6), nullable=True),
        sa.Column("pct_change", sa.Numeric(12, 6), nullable=True),
        sa.Column("volume", sa.Numeric(24, 4), nullable=True),
        sa.Column("amount", sa.Numeric(24, 4), nullable=True),
        sa.Column("turnover_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("volume_ratio", sa.Numeric(12, 6), nullable=True),
        sa.Column("total_market_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("circulating_market_value", sa.Numeric(24, 4), nullable=True),
        sa.Column("pe_ttm", sa.Numeric(18, 6), nullable=True),
        sa.Column("pb", sa.Numeric(18, 6), nullable=True),
        sa.Column("is_trading", sa.Boolean(), nullable=True),
        sa.Column("data_completeness", sa.String(length=32), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_metadata_hash", sa.String(length=64), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("source_record_ref", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "data_completeness IN ('complete', 'usable', 'partial', 'insufficient')",
            name=op.f("ck_stock_daily_snapshots_stock_daily_snapshots_completeness_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_stock_daily_snapshots_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_daily_snapshots")),
        sa.UniqueConstraint(
            "stock_id",
            "trade_date",
            "source_code",
            name=op.f("uq_stock_daily_snapshots_stock_date_source"),
        ),
    )
    op.create_index(
        "ix_stock_daily_snapshots_stock_date",
        "stock_daily_snapshots",
        ["stock_id", "trade_date"],
    )
    op.create_index(
        "ix_stock_daily_snapshots_source_date",
        "stock_daily_snapshots",
        ["source_code", "trade_date"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO market_data_sources (
                id, source_code, display_name, source_type, authorization_status,
                usage_scope, production_enabled, capabilities, last_health_status,
                last_health_checked_at, limitations, created_at, updated_at
            )
            VALUES (
                '00000000-0000-0000-0000-000000000301',
                'TUSHARE_PRO',
                'Tushare Pro',
                'third_party_data_service',
                'unverified',
                '["local_development", "internal_testing"]'::json,
                false,
                '["daily_snapshot", "trade_calendar"]'::json,
                'unknown',
                NULL,
                '["开发验证候选；个人 Token 不等于生产授权；公开展示、再分发和商业使用必须另行确认。"]'::json,
                now(),
                now()
            )
            ON CONFLICT (source_code) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                source_type = EXCLUDED.source_type,
                authorization_status = EXCLUDED.authorization_status,
                usage_scope = EXCLUDED.usage_scope,
                production_enabled = EXCLUDED.production_enabled,
                capabilities = EXCLUDED.capabilities,
                limitations = EXCLUDED.limitations,
                updated_at = now()
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO external_sources (
                id, source_code, display_name, publisher_name, source_category,
                authority_level, source_tier, jurisdiction, country_code, region_code,
                city_code, official_domain, access_mode, content_language,
                provider_adapter, authorization_status, redistribution_status,
                commercial_use_status, legal_review_status, health_status, enabled,
                experimental, limitations, created_at, updated_at
            )
            VALUES (
                '00000000-0000-0000-0000-000000000103',
                'BSE_DISCLOSURE',
                '北交所上市公司公告',
                '北京证券交易所',
                'exchange_announcement',
                'exchange',
                's',
                'CN',
                'CN',
                'BJ',
                NULL,
                'bse.cn',
                'public_endpoint',
                'zh-CN',
                'bse',
                'review_required',
                'unclear',
                'unclear',
                'pending',
                'unknown',
                false,
                true,
                '["北交所官方公开公告候选；真实网络可达性、字段稳定性和使用授权仍需补验。"]'::json,
                now(),
                now()
            )
            ON CONFLICT (source_code) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                publisher_name = EXCLUDED.publisher_name,
                source_category = EXCLUDED.source_category,
                authority_level = EXCLUDED.authority_level,
                source_tier = EXCLUDED.source_tier,
                jurisdiction = EXCLUDED.jurisdiction,
                country_code = EXCLUDED.country_code,
                region_code = EXCLUDED.region_code,
                official_domain = EXCLUDED.official_domain,
                access_mode = EXCLUDED.access_mode,
                content_language = EXCLUDED.content_language,
                provider_adapter = EXCLUDED.provider_adapter,
                authorization_status = EXCLUDED.authorization_status,
                redistribution_status = EXCLUDED.redistribution_status,
                commercial_use_status = EXCLUDED.commercial_use_status,
                legal_review_status = EXCLUDED.legal_review_status,
                experimental = EXCLUDED.experimental,
                limitations = EXCLUDED.limitations,
                updated_at = now()
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM external_sources WHERE source_code = 'BSE_DISCLOSURE'"))
    op.execute(sa.text("DELETE FROM market_data_sources WHERE source_code = 'TUSHARE_PRO'"))
    op.drop_index("ix_stock_daily_snapshots_source_date", table_name="stock_daily_snapshots")
    op.drop_index("ix_stock_daily_snapshots_stock_date", table_name="stock_daily_snapshots")
    op.drop_table("stock_daily_snapshots")
    op.drop_index("ix_market_data_sync_runs_resolved_date", table_name="market_data_sync_runs")
    op.drop_index("uq_market_data_sync_runs_active_source_date", table_name="market_data_sync_runs")
    op.drop_index("ix_market_data_sync_runs_requested_date", table_name="market_data_sync_runs")
    op.drop_index("ix_market_data_sync_runs_source_started", table_name="market_data_sync_runs")
    op.drop_table("market_data_sync_runs")
    op.drop_index("ix_market_data_sources_production_enabled", table_name="market_data_sources")
    op.drop_index("uq_market_data_sources_source_code", table_name="market_data_sources")
    op.drop_table("market_data_sources")
