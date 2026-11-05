import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DB = "chat_test"
os.environ["POSTGRES_DB"] = TEST_DB
os.environ["POSTGRES_USER"] = "chat_user"
os.environ["POSTGRES_PASSWORD"] = "chat_pass"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5437"

if not TEST_DB.endswith("_test"):
    raise RuntimeError(
        f"pytest отказывается открыть базу {TEST_DB!r}: имя должно кончаться на _test"
    )


@pytest.fixture(scope="session")
def migrated() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=os.environ.copy(),
        check=True,
    )


@pytest.fixture(autouse=True)
async def clean_tables(migrated: None) -> AsyncIterator[None]:
    yield
    from app.config import settings

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE messages, rooms, user_profiles RESTART IDENTITY CASCADE"))
    await engine.dispose()
