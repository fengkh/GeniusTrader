"""add_session_csrf_protection

Revision ID: 202607230003
Revises: 202607230002
Create Date: 2026-07-23 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230003"
down_revision: str | None = "202607230002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_sessions", sa.Column("csrf_token_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("user_sessions", "csrf_token_hash")
