from __future__ import annotations

from typing import Protocol


class EmbeddingService(Protocol):
    """Port for generating embeddings (Azure OpenAI text-embedding-3-small, 1536 dims).

    Used both offline (catalog seeding, business-logic-model.md Section 1) and online
    (per-request ProfileQuery, step 5)."""

    async def embed(self, text: str) -> tuple[float, ...]: ...
