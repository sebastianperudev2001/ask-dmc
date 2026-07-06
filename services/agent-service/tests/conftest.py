from __future__ import annotations

import os

import pytest
import pytest_asyncio

from src.adapters.connection_pool import ConnectionPool

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set — skipping tests that require a real Postgres+pgvector instance",
)


@pytest_asyncio.fixture
async def connection_pool():
    pool = ConnectionPool(TEST_DATABASE_URL, min_size=1, max_size=2, require_ssl=False)
    await pool.start()
    yield pool
    await pool.close()
