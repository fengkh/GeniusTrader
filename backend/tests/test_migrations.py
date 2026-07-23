# ruff: noqa: I001
from alembic import command
from alembic.config import Config

from tests.conftest import BACKEND_ROOT


def test_alembic_current_is_head(migrated_test_database):
    del migrated_test_database
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.check(alembic_cfg)
