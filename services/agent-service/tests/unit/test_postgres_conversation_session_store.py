"""Tests against a REAL Postgres instance (migrations/002_create_leads_and_sessions.sql
must already be applied — conversation_sessions table). Requires TEST_DATABASE_URL;
skipped otherwise."""
from __future__ import annotations

import pytest

from src.adapters.postgres_conversation_session_store import PostgresConversationSessionStore
from tests.conftest import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


async def test_set_and_get_service_session_id(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_sessions")
    store = PostgresConversationSessionStore(connection_pool)

    await store.set_service_session_id("conv-1", "resp_abc")

    assert await store.get_service_session_id("conv-1") == "resp_abc"


async def test_set_upserts_existing_conversation_id(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_sessions")
    store = PostgresConversationSessionStore(connection_pool)

    await store.set_service_session_id("conv-1", "resp_first")
    await store.set_service_session_id("conv-1", "resp_second")

    assert await store.get_service_session_id("conv-1") == "resp_second"


async def test_get_returns_none_for_unknown_conversation(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_sessions")
    store = PostgresConversationSessionStore(connection_pool)

    assert await store.get_service_session_id("nonexistent") is None
