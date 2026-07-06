"""Tests against a REAL Postgres instance (migrations/003_create_conversation_messages.sql
must already be applied). Requires TEST_DATABASE_URL env var; skipped otherwise — same
pattern as test_postgres_lead_repository.py."""
from __future__ import annotations

import pytest

from src.adapters.postgres_conversation_message_repository import (
    PostgresConversationMessageRepository,
)
from src.domain.models import MessageRole
from tests.conftest import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]


async def test_append_and_get_messages_in_order(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_messages")
    repo = PostgresConversationMessageRepository(connection_pool)

    await repo.append("conv-1", MessageRole.USER, "hola")
    await repo.append("conv-1", MessageRole.BOT, "hola, en que te ayudo?")
    await repo.append("conv-2", MessageRole.USER, "mensaje de otra conversacion")

    messages = await repo.get_messages("conv-1")

    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[0].content == "hola"
    assert messages[1].role == MessageRole.BOT
    assert messages[1].content == "hola, en que te ayudo?"


async def test_get_messages_returns_empty_list_for_unknown_conversation(connection_pool):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_messages")
    repo = PostgresConversationMessageRepository(connection_pool)

    assert await repo.get_messages("nonexistent") == []


async def test_list_conversations_orders_by_last_activity_desc_with_first_user_message_as_preview(
    connection_pool,
):
    await connection_pool.pool.execute("TRUNCATE TABLE conversation_messages")
    repo = PostgresConversationMessageRepository(connection_pool)

    # conv-A started first, but gets a follow-up message AFTER conv-B was created —
    # so conv-A's last activity ends up more recent than conv-B's, and it should sort
    # first despite being the older conversation.
    await repo.append("conv-a", MessageRole.USER, "pregunta de A")
    await repo.append("conv-a", MessageRole.BOT, "respuesta de A")
    await repo.append("conv-b", MessageRole.USER, "pregunta de B")
    await repo.append("conv-a", MessageRole.USER, "segunda pregunta de A")

    summaries = await repo.list_conversations()

    assert [s.conversation_id for s in summaries] == ["conv-a", "conv-b"]
    # Preview is always the FIRST user message, not the most recent one.
    assert summaries[0].preview == "pregunta de A"
    assert summaries[1].preview == "pregunta de B"
