"""create_core_users_and_watchlist

Revision ID: 202607230001
Revises:
Create Date: 2026-07-23 00:00:00.000000
"""

# ruff: noqa: I001

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202607230001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns(include_updated: bool = True) -> list[sa.Column]:
    columns = [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    ]
    if include_updated:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            )
        )
    return columns


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint("role IN ('admin', 'user')", name=op.f("ck_users_users_role_allowed")),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'locked')",
            name=op.f("ck_users_users_status_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)

    op.create_table(
        "user_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_credentials")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_credentials_user_id")),
    )
    op.create_index(op.f("ix_user_credentials_user_id"), "user_credentials", ["user_id"])

    op.create_table(
        "stocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("exchange", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("list_status", sa.String(length=16), nullable=False),
        sa.Column("list_date", sa.Date(), nullable=True),
        sa.Column("delist_date", sa.Date(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("data_source", sa.String(length=64), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stocks")),
        sa.UniqueConstraint("symbol", "exchange", name="uq_stocks_symbol_exchange"),
    )
    op.create_index("ix_stocks_name", "stocks", ["name"], unique=False)
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"], unique=False)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        *timestamp_columns(include_updated=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
    )
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)
    op.create_index("ix_user_sessions_user_id_expires_at", "user_sessions", ["user_id", "expires_at"])

    op.create_table(
        "watchlist_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("sort_order >= 0", name=op.f("ck_watchlist_groups_watchlist_groups_sort_order_non_negative")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_watchlist_groups_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlist_groups")),
    )
    op.create_index("ix_watchlist_groups_user_id", "watchlist_groups", ["user_id"], unique=False)
    op.create_index("uq_watchlist_groups_user_name", "watchlist_groups", ["user_id", "name"], unique=True)
    op.create_index(
        "uq_watchlist_groups_one_default",
        "watchlist_groups",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )

    op.create_table(
        "user_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_tags_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_tags")),
    )
    op.create_index("ix_user_tags_user_id", "user_tags", ["user_id"], unique=False)
    op.create_index("uq_user_tags_user_name", "user_tags", ["user_id", "name"], unique=True)

    op.create_table(
        "user_watchlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("stock_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("attention_reason", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_user_watchlist_items_user_watchlist_items_sort_order_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["watchlist_groups.id"],
            name=op.f("fk_user_watchlist_items_group_id_watchlist_groups"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["stock_id"],
            ["stocks.id"],
            name=op.f("fk_user_watchlist_items_stock_id_stocks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_watchlist_items_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_watchlist_items")),
    )
    op.create_index("ix_user_watchlist_items_stock_id", "user_watchlist_items", ["stock_id"])
    op.create_index("ix_user_watchlist_items_user_id", "user_watchlist_items", ["user_id"])
    op.create_index(
        "ix_user_watchlist_items_user_sort",
        "user_watchlist_items",
        ["user_id", "sort_order", "created_at"],
    )
    op.create_index(
        "uq_user_watchlist_items_active_stock",
        "user_watchlist_items",
        ["user_id", "stock_id"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "watchlist_item_tags",
        sa.Column("watchlist_item_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        *timestamp_columns(include_updated=False),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["user_tags.id"],
            name=op.f("fk_watchlist_item_tags_tag_id_user_tags"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["watchlist_item_id"],
            ["user_watchlist_items.id"],
            name=op.f("fk_watchlist_item_tags_watchlist_item_id_user_watchlist_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("watchlist_item_id", "tag_id", name=op.f("pk_watchlist_item_tags")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_user_id", "created_at"])
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("watchlist_item_tags")
    op.drop_index("uq_user_watchlist_items_active_stock", table_name="user_watchlist_items")
    op.drop_index("ix_user_watchlist_items_user_sort", table_name="user_watchlist_items")
    op.drop_index("ix_user_watchlist_items_user_id", table_name="user_watchlist_items")
    op.drop_index("ix_user_watchlist_items_stock_id", table_name="user_watchlist_items")
    op.drop_table("user_watchlist_items")
    op.drop_index("uq_user_tags_user_name", table_name="user_tags")
    op.drop_index("ix_user_tags_user_id", table_name="user_tags")
    op.drop_table("user_tags")
    op.drop_index("uq_watchlist_groups_one_default", table_name="watchlist_groups")
    op.drop_index("uq_watchlist_groups_user_name", table_name="watchlist_groups")
    op.drop_index("ix_watchlist_groups_user_id", table_name="watchlist_groups")
    op.drop_table("watchlist_groups")
    op.drop_index("ix_user_sessions_user_id_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_stocks_symbol", table_name="stocks")
    op.drop_index("ix_stocks_name", table_name="stocks")
    op.drop_table("stocks")
    op.drop_index(op.f("ix_user_credentials_user_id"), table_name="user_credentials")
    op.drop_table("user_credentials")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
