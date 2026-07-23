import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_core_tables_exist(db_session):
    rows = (
        await db_session.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'users',
                    'user_credentials',
                    'user_sessions',
                    'stocks',
                    'watchlist_groups',
                    'user_watchlist_items',
                    'user_tags',
                    'watchlist_item_tags',
                    'audit_logs'
                  )
                """
            )
        )
    ).scalars().all()
    assert set(rows) == {
        "users",
        "user_credentials",
        "user_sessions",
        "stocks",
        "watchlist_groups",
        "user_watchlist_items",
        "user_tags",
        "watchlist_item_tags",
        "audit_logs",
    }


@pytest.mark.asyncio
async def test_test_database_isolated_from_development(db_session):
    database_name = (await db_session.execute(text("SELECT current_database()"))).scalar_one()
    assert database_name == "geniustrader_test"
