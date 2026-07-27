"""create_security_master

Revision ID: 202607230006
Revises: 202607230005
Create Date: 2026-07-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230006"
down_revision: str | None = "202607230005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


SECURITY_MASTER_SYNC_STATUS_VALUES = (
    "'running', 'complete', 'partial', 'failed', 'data_insufficient', 'not_available', "
    "'network_error', 'timeout', 'rate_limited', 'access_denied', 'source_changed', "
    "'parse_error', 'content_unavailable', 'legal_hold', 'disabled'"
)


def upgrade() -> None:
    op.add_column("stocks", sa.Column("code", sa.String(length=16), nullable=True))
    op.add_column("stocks", sa.Column("board", sa.String(length=32), nullable=True))
    op.add_column("stocks", sa.Column("security_type", sa.String(length=32), nullable=True))
    op.add_column("stocks", sa.Column("short_name", sa.String(length=100), nullable=True))
    op.add_column("stocks", sa.Column("full_name", sa.String(length=200), nullable=True))
    op.add_column("stocks", sa.Column("english_name", sa.String(length=200), nullable=True))
    op.add_column("stocks", sa.Column("listing_status", sa.String(length=32), nullable=True))
    op.add_column("stocks", sa.Column("listed_at", sa.Date(), nullable=True))
    op.add_column("stocks", sa.Column("delisted_at", sa.Date(), nullable=True))
    op.add_column("stocks", sa.Column("aliases", sa.JSON(), nullable=True))
    op.add_column("stocks", sa.Column("pinyin", sa.String(length=200), nullable=True))
    op.add_column("stocks", sa.Column("pinyin_initials", sa.String(length=64), nullable=True))
    op.add_column("stocks", sa.Column("source_code", sa.String(length=80), nullable=True))
    op.add_column("stocks", sa.Column("source_record_id", sa.String(length=160), nullable=True))
    op.add_column("stocks", sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stocks", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stocks", sa.Column("data_completeness", sa.String(length=32), nullable=True))
    op.add_column("stocks", sa.Column("is_searchable", sa.Boolean(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE stocks
            SET
                code = CASE WHEN position('.' in symbol) > 0 THEN split_part(symbol, '.', 1) ELSE symbol END,
                board = CASE
                    WHEN exchange = 'SH' AND symbol LIKE '688%' THEN 'star_board'
                    WHEN exchange = 'SZ' AND symbol LIKE '300%' THEN 'chinext'
                    WHEN exchange = 'BJ' THEN 'bse'
                    ELSE 'main_board'
                END,
                security_type = 'common_stock',
                short_name = name,
                full_name = name,
                listing_status = CASE
                    WHEN list_status IN ('listed', 'active') THEN 'active'
                    WHEN list_status = 'delisted' THEN 'delisted'
                    ELSE 'unknown'
                END,
                listed_at = list_date,
                delisted_at = delist_date,
                aliases = '[]'::json,
                pinyin = CASE name
                    WHEN '贵州茅台' THEN 'guizhoumaotai'
                    WHEN '平安银行' THEN 'pinganyinhang'
                    WHEN '宁德时代' THEN 'ningdeshidai'
                    WHEN '中芯国际' THEN 'zhongxinguoji'
                    ELSE NULL
                END,
                pinyin_initials = CASE name
                    WHEN '贵州茅台' THEN 'gzmt'
                    WHEN '平安银行' THEN 'payh'
                    WHEN '宁德时代' THEN 'ndsd'
                    WHEN '中芯国际' THEN 'zxgj'
                    ELSE NULL
                END,
                source_code = data_source,
                source_record_id = CASE WHEN data_source = 'development_seed' THEN symbol ELSE NULL END,
                last_synced_at = updated_at,
                data_completeness = CASE WHEN data_source = 'development_seed' THEN 'partial' ELSE 'usable' END,
                is_searchable = true
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE stocks
            SET symbol = code || '.' || exchange
            WHERE position('.' in symbol) = 0
            """
        )
    )

    for column in [
        "code",
        "board",
        "security_type",
        "short_name",
        "listing_status",
        "aliases",
        "source_code",
        "data_completeness",
        "is_searchable",
    ]:
        op.alter_column("stocks", column, nullable=False)

    op.drop_constraint("uq_stocks_symbol_exchange", "stocks", type_="unique")
    op.create_unique_constraint("uq_stocks_symbol", "stocks", ["symbol"])
    op.create_unique_constraint("uq_stocks_exchange_code", "stocks", ["exchange", "code"])
    op.create_index("ix_stocks_code", "stocks", ["code"])
    op.create_index("ix_stocks_short_name", "stocks", ["short_name"])
    op.create_index("ix_stocks_listing_status", "stocks", ["listing_status"])
    op.create_index("ix_stocks_searchable", "stocks", ["is_searchable"])

    op.create_table(
        "security_master_sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("exchanges", sa.JSON(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("deactivated_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            f"status IN ({SECURITY_MASTER_SYNC_STATUS_VALUES})",
            name=op.f("ck_security_master_sync_runs_security_master_sync_runs_status_allowed"),
        ),
        sa.CheckConstraint("request_count >= 0", name=op.f("ck_security_master_sync_runs_security_master_sync_runs_request_count_non_negative")),
        sa.CheckConstraint("received_count >= 0", name=op.f("ck_security_master_sync_runs_security_master_sync_runs_received_count_non_negative")),
        sa.CheckConstraint("created_count >= 0", name=op.f("ck_security_master_sync_runs_security_master_sync_runs_created_count_non_negative")),
        sa.CheckConstraint("updated_count >= 0", name=op.f("ck_security_master_sync_runs_security_master_sync_runs_updated_count_non_negative")),
        sa.CheckConstraint("unchanged_count >= 0", name=op.f("ck_security_master_sync_runs_security_master_sync_runs_unchanged_count_non_negative")),
        sa.CheckConstraint("deactivated_count >= 0", name=op.f("ck_security_master_sync_runs_security_master_sync_runs_deactivated_count_non_negative")),
        sa.CheckConstraint("failure_count >= 0", name=op.f("ck_security_master_sync_runs_security_master_sync_runs_failure_count_non_negative")),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.id"],
            name=op.f("fk_security_master_sync_runs_triggered_by_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_master_sync_runs")),
    )
    op.create_index("ix_security_master_sync_runs_source_started", "security_master_sync_runs", ["source_code", "started_at"])
    op.create_index("ix_security_master_sync_runs_triggered", "security_master_sync_runs", ["triggered_by_user_id", "started_at"])

    op.create_table(
        "security_source_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stock_id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("provider_security_id", sa.String(length=160), nullable=False),
        sa.Column("source_symbol", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("raw_metadata_hash", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_status", sa.String(length=40), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_security_source_records_stock_id_stocks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_source_records")),
    )
    op.create_index("ix_security_source_records_stock", "security_source_records", ["stock_id"])
    op.create_index("ix_security_source_records_source_status", "security_source_records", ["source_code", "source_status"])
    op.create_index(
        "uq_security_source_records_provider_id",
        "security_source_records",
        ["source_code", "provider_security_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_security_source_records_provider_id", table_name="security_source_records")
    op.drop_index("ix_security_source_records_source_status", table_name="security_source_records")
    op.drop_index("ix_security_source_records_stock", table_name="security_source_records")
    op.drop_table("security_source_records")
    op.drop_index("ix_security_master_sync_runs_triggered", table_name="security_master_sync_runs")
    op.drop_index("ix_security_master_sync_runs_source_started", table_name="security_master_sync_runs")
    op.drop_table("security_master_sync_runs")

    op.drop_index("ix_stocks_searchable", table_name="stocks")
    op.drop_index("ix_stocks_listing_status", table_name="stocks")
    op.drop_index("ix_stocks_short_name", table_name="stocks")
    op.drop_index("ix_stocks_code", table_name="stocks")
    op.drop_constraint("uq_stocks_exchange_code", "stocks", type_="unique")
    op.drop_constraint("uq_stocks_symbol", "stocks", type_="unique")
    op.execute(sa.text("UPDATE stocks SET symbol = code WHERE code IS NOT NULL"))
    op.create_unique_constraint("uq_stocks_symbol_exchange", "stocks", ["symbol", "exchange"])

    for column in [
        "is_searchable",
        "data_completeness",
        "last_synced_at",
        "source_updated_at",
        "source_record_id",
        "source_code",
        "pinyin_initials",
        "pinyin",
        "aliases",
        "delisted_at",
        "listed_at",
        "listing_status",
        "english_name",
        "full_name",
        "short_name",
        "security_type",
        "board",
        "code",
    ]:
        op.drop_column("stocks", column)
