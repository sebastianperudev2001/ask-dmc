"""Property/example tests for RetryPolicy (PATTERN-01)."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.adapters.retry_policy import RetryPolicy


@pytest.mark.asyncio
@given(failures_before_success=st.integers(min_value=0, max_value=2))
@settings(max_examples=10, deadline=None)
async def test_retry_succeeds_if_within_max_attempts(failures_before_success):
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.001)
    calls = {"count": 0}

    async def flaky_operation() -> str:
        calls["count"] += 1
        if calls["count"] <= failures_before_success:
            raise RuntimeError("transient failure")
        return "ok"

    result = await policy.run(flaky_operation)
    assert result == "ok"
    assert calls["count"] == failures_before_success + 1


@pytest.mark.asyncio
async def test_retry_raises_after_exhausting_max_attempts():
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.001)
    calls = {"count": 0}

    async def always_failing_operation() -> str:
        calls["count"] += 1
        raise RuntimeError("persistent failure")

    with pytest.raises(RuntimeError, match="persistent failure"):
        await policy.run(always_failing_operation)
    assert calls["count"] == 3
