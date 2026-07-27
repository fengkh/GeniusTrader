"""add_daily_review_generation_guard

Revision ID: 202607230007
Revises: 202607230006
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230007"
down_revision: str | None = "202607230006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_ai_tasks_active_daily_review_generation",
        "ai_tasks",
        ["target_id"],
        unique=True,
        postgresql_where=sa.text(
            "task_type = 'user_daily_review_generation' "
            "AND target_type = 'daily_review' "
            "AND status IN ('pending', 'running')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_ai_tasks_active_daily_review_generation", table_name="ai_tasks")
