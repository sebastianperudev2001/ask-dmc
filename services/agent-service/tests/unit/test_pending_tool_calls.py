"""Tests for PendingToolCallRegistry (PATTERN-15) — registration, resolution, and
cancellation on connection close."""
from __future__ import annotations

import asyncio

import pytest

from src.domain.pending_tool_calls import PendingToolCallRegistry


async def test_resolve_completes_the_matching_future():
    registry = PendingToolCallRegistry()
    future = registry.create("call_1")

    resolved = registry.resolve("call_1", {"budget": 500.0})
    assert resolved is True
    assert await future == {"budget": 500.0}


def test_resolve_returns_false_for_unknown_call_id():
    registry = PendingToolCallRegistry()
    assert registry.resolve("nonexistent", "anything") is False


async def test_resolve_returns_false_for_already_resolved_call_id():
    registry = PendingToolCallRegistry()
    registry.create("call_1")
    registry.resolve("call_1", "first")

    assert registry.resolve("call_1", "second") is False


async def test_cancel_all_cancels_pending_futures():
    registry = PendingToolCallRegistry()
    future = registry.create("call_1")

    registry.cancel_all()

    with pytest.raises(asyncio.CancelledError):
        await future


async def test_cancel_all_does_not_raise_on_already_resolved_futures():
    registry = PendingToolCallRegistry()
    future = registry.create("call_1")
    registry.resolve("call_1", "done")

    registry.cancel_all()  # must not touch a completed future

    assert await future == "done"
